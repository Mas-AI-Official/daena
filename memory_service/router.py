"""
Hybrid memory router coordinating legacy storage with the NBMF tiers.
"""

from __future__ import annotations

import os
import random
from dataclasses import asdict, dataclass
from time import perf_counter, process_time
from typing import Any, Callable, Dict, List, Optional, Tuple

from .adapters.l1_embeddings import L1Index
from .adapters.l2_nbmf_store import L2Store
from .adapters.l3_cold_store import L3Store
from .legacy_store import LegacyStore
from .ledger import log_event
from .memory_bootstrap import load_config
from .metrics import incr, incr_operation, observe, observe_cpu_time
from .policy import AccessPolicy
from .quarantine_l2q import L2Quarantine
from .trust_manager import TrustManager

# Optional knowledge distillation
try:
    from .knowledge_distillation import knowledge_distiller
    DISTILLATION_AVAILABLE = True
except ImportError:
    DISTILLATION_AVAILABLE = False
    knowledge_distiller = None

# Optional OCR service for baseline comparison
try:
    from .ocr_service import OCRService, OCRProvider
    OCR_SERVICE_AVAILABLE = True
except ImportError:
    OCR_SERVICE_AVAILABLE = False
    OCRService = None
    OCRProvider = None

# Optional tracing support
try:
    from backend.utils.tracing import get_tracing_service, trace_nbmf_operation
    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False
    def trace_nbmf_operation(*args, **kwargs):
        pass


@dataclass
class RouterFlags:
    nbmf_enabled: bool
    dual_write: bool
    read_mode: str
    canary_percent: float
    tenant_allowlist: List[str]
    divergence_abort: bool
    legacy_read_through: bool


class MemoryRouter:
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        legacy_store: Optional[LegacyStore] = None,
        canary_selector: Optional[Callable[[], float]] = None,
        enable_ocr_comparison: bool = False,
    ) -> None:
        self._config = config or load_config()
        self._legacy = legacy_store or LegacyStore()
        self.l1 = L1Index()
        self.l2 = L2Store()
        self.l3 = L3Store()
        self.l2q = L2Quarantine()
        self.canary_selector = canary_selector or (lambda: random.random())
        self._flags = self._load_flags()
        self.trust = TrustManager()
        self.policy = AccessPolicy()
        
        # OCR comparison integration (optional)
        self.enable_ocr_comparison = enable_ocr_comparison
        if enable_ocr_comparison and OCR_SERVICE_AVAILABLE:
            try:
                from .ocr_comparison_integration import get_ocr_comparison, OCRProvider
                self.ocr_comparison = get_ocr_comparison(
                    ocr_provider=OCRProvider.TESSERACT,
                    confidence_threshold=0.7,
                    enable_hybrid=True
                )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"OCR comparison integration failed: {e}")
                self.ocr_comparison = None
        else:
            self.ocr_comparison = None

    # ------------------------------------------------------------------
    # Flags & config management
    # ------------------------------------------------------------------
    def _env_bool(self, key: str, default: bool) -> bool:
        value = os.getenv(key)
        if value is None:
            return default
        return value.lower() in {"1", "true", "yes", "on"}

    def _env_float(self, key: str, default: float) -> float:
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return float(value)
        except ValueError:
            return default

    def _env_list(self, key: str, default: List[str]) -> List[str]:
        value = os.getenv(key)
        if value is None:
            return default
        return [item.strip() for item in value.split(",") if item.strip()]

    def _load_flags(self) -> RouterFlags:
        cfg_flags = dict(self._config.get("flags", {}))
        defaults = {
            "nbmf_enabled": True,
            "dual_write": False,
            "read_mode": cfg_flags.get("read_mode", "nbmf"),
            "canary_percent": float(cfg_flags.get("canary_percent", 100)),
            "tenant_allowlist": list(cfg_flags.get("tenant_allowlist", [])),
            "divergence_abort": bool(cfg_flags.get("divergence_abort", True)),
        }

        nbmf_enabled = self._env_bool("DAENA_NBMF_ENABLED", defaults["nbmf_enabled"])
        dual_write = self._env_bool("DAENA_DUAL_WRITE", defaults["dual_write"])
        read_mode = os.getenv("DAENA_READ_MODE", defaults["read_mode"]).lower()
        canary_percent = max(0.0, min(100.0, self._env_float("DAENA_CANARY_PERCENT", defaults["canary_percent"])))
        allowlist = self._env_list("DAENA_TENANT_ALLOWLIST", defaults["tenant_allowlist"])
        divergence_abort = self._env_bool("DAENA_DIVERGENCE_ABORT", defaults["divergence_abort"])
        legacy_read_through = self._env_bool("DAENA_LEGACY_READ_THROUGH", bool(cfg_flags.get("legacy_read_through", True)))

        return RouterFlags(
            nbmf_enabled=nbmf_enabled,
            dual_write=dual_write,
            read_mode=read_mode or "nbmf",
            canary_percent=canary_percent,
            tenant_allowlist=allowlist,
            divergence_abort=divergence_abort,
            legacy_read_through=legacy_read_through,
        )

    def refresh(self) -> None:
        self._config = load_config()
        self._flags = self._load_flags()

    @property
    def config(self) -> Dict[str, Any]:
        return dict(self._config)

    @property
    def flags(self) -> Dict[str, Any]:
        return asdict(self._flags)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _nbmf_primary(self) -> bool:
        if os.getenv("DAENA_READ_MODE", "").lower() == "nbmf":
            return True
        return self._flags.nbmf_enabled and self._flags.read_mode == "nbmf"

    def _should_use_nbmf(self, tenant: Optional[str]) -> bool:
        if self._flags.read_mode == "nbmf":
            return True
        if self._flags.read_mode == "legacy":
            return False
        if tenant and tenant in set(self._flags.tenant_allowlist):
            return True
        threshold = self._flags.canary_percent / 100.0
        return self.canary_selector() < threshold

    def _tenant_from_context(self, meta: Optional[Dict[str, Any]], policy_ctx: Optional[Dict[str, Any]]) -> str:
        if policy_ctx and policy_ctx.get("tenant_id"):
            return str(policy_ctx["tenant_id"])
        if meta and meta.get("tenant_id"):
            return str(meta["tenant_id"])
        return "default"

    def _fidelity_for_class(self, cls: str) -> str:
        fidelity_cfg = self._config.get("memory_policy", {}).get("fidelity", {})
        for key, rule in fidelity_cfg.items():
            classes = [name.strip() for name in key.split("|")]
            if cls in classes:
                return str(rule.get("mode", "semantic"))
        return "semantic"

    def _tenant_profile(self, tenant: str) -> Tuple[str, Dict[str, Any]]:
        tenants_cfg = self._config.get("tenants", {})
        if tenant in tenants_cfg:
            return tenant, tenants_cfg[tenant]
        if "default" in tenants_cfg:
            return "default", tenants_cfg["default"]
        return tenant, {}

    def _apply_compression_policy(
        self,
        cls: str,
        meta: Dict[str, Any],
        policy_ctx: Optional[Dict[str, Any]],
    ) -> str:
        tenant = self._tenant_from_context(meta, policy_ctx)
        mode = self._fidelity_for_class(cls)
        profile_name, profile = self._tenant_profile(tenant)
        compression_cfg = profile.get("compression", {})
        settings = compression_cfg.get(mode, compression_cfg.get("default", {}))
        meta.setdefault("compression", {})
        meta["compression"].update(
            {
                "mode": mode,
                "profile": profile_name,
                "settings": settings,
            }
        )
        if "usage_alert_bytes" in profile:
            meta["compression"]["usage_alert_bytes"] = profile["usage_alert_bytes"]
        meta["tenant_id"] = tenant
        return tenant

    def _policy_context(
        self,
        meta: Optional[Dict[str, Any]],
        policy_ctx: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        ctx: Dict[str, Any] = {}
        if meta:
            if meta.get("tenant_id"):
                ctx.setdefault("tenant_id", meta["tenant_id"])
            ctx.update(meta.get("policy_context") or {})
        if policy_ctx:
            ctx.update(policy_ctx)
        return ctx or None

    def _evaluate_divergence(
        self,
        item_id: str,
        cls: str,
        payload: Any,
        existing_full: Dict[str, Any],
        meta: Dict[str, Any],
    ) -> None:
        assessment = self.trust.assess(
            cls,
            payload,
            reference=existing_full.get("payload"),
            hallucination_scores=meta.get("hallucination_scores"),
            related_texts=meta.get("related_texts"),
        )
        if assessment.divergence <= 0.0:
            return
        incr("divergence_events")
        log_event(
            action="divergence",
            ref=item_id,
            store="nbmf",
            route="compare",
            extra={
                "cls": cls,
                "divergence": round(assessment.divergence, 4),
                "score": round(assessment.score, 4),
                "issues": assessment.issues,
            },
        )
        if self._flags.divergence_abort and self.trust.requires_abort(cls, assessment.divergence):
            log_event(
                action="divergence_abort",
                ref=item_id,
                store="nbmf",
                route="compare",
                extra={
                    "cls": cls,
                    "divergence": round(assessment.divergence, 4),
                    "issues": assessment.issues,
                },
            )
            raise RuntimeError(f"Divergence threshold exceeded for {cls}:{item_id}")

    def _index_payload(self, item_id: str, payload: Any, cls: str) -> None:
        try:
            self.l1.index(item_id, payload, {"cls": cls})
        except Exception:  # pragma: no cover - best effort
            pass

    def _attach_meta(self, payload: Any, meta: Dict[str, Any]) -> Any:
        if not meta:
            return payload
        if isinstance(payload, dict):
            merged = dict(payload)
            merged.setdefault("__meta__", meta)
            return merged
        return {"value": payload, "__meta__": meta}

    def _update_access_metadata(self, item_id: str, cls: str, meta: Dict[str, Any]) -> None:
        """Update access tracking metadata for aging/rebalancing."""
        import time
        meta["last_accessed"] = time.time()
        access_count = meta.get("access_count", 0)
        meta["access_count"] = access_count + 1
        # Update in L2 if record exists there
        try:
            if self.l2.exists(item_id, cls):
                full = self.l2.get_full_record(item_id, cls)
                if full:
                    full["meta"] = meta
                    self.l2.put_record(item_id, cls, full.get("payload"), meta)
        except Exception:
            # Best effort - don't fail reads if metadata update fails
            pass

    def _detect_content_type(self, payload: Any) -> Dict[str, Any]:
        """
        Detect content type for multimodal support.
        
        Returns:
            Dict with content_type, is_binary, mime_type, etc.
        """
        import mimetypes
        import base64
        from pathlib import Path
        
        result = {
            "content_type": "text",
            "is_binary": False,
            "mime_type": "text/plain",
        }
        
        if isinstance(payload, dict):
            # Check for common binary indicators
            if "image" in payload or "audio" in payload or "video" in payload:
                result["content_type"] = "multimodal"
            if "data" in payload and "mime_type" in payload:
                result["mime_type"] = payload["mime_type"]
                result["is_binary"] = True
                result["content_type"] = "binary"
        elif isinstance(payload, str):
            # Check if it's a file path
            if payload.startswith("file://") or Path(payload).exists():
                path = Path(payload.replace("file://", ""))
                mime_type, _ = mimetypes.guess_type(str(path))
                if mime_type:
                    result["mime_type"] = mime_type
                    if mime_type.startswith(("image/", "audio/", "video/")):
                        result["content_type"] = "multimodal"
                        result["is_binary"] = True
        elif isinstance(payload, bytes):
            result["content_type"] = "binary"
            result["is_binary"] = True
            result["mime_type"] = "application/octet-stream"
        
        return result

    def _encode_multimodal(self, payload: Any, content_info: Dict[str, Any]) -> Any:
        """
        Encode multimodal content (images, audio, etc.) for storage.
        
        Args:
            payload: Original payload (may be bytes, file path, or dict)
            content_info: Content type information from _detect_content_type()
        
        Returns:
            Encoded payload suitable for JSON storage
        """
        import base64
        from pathlib import Path
        
        if not content_info.get("is_binary"):
            return payload  # Text content, no encoding needed
        
        # Handle bytes directly
        if isinstance(payload, bytes):
            encoded = base64.b64encode(payload).decode("ascii")
            return {
                "__multimodal__": True,
                "mime_type": content_info["mime_type"],
                "content_type": content_info["content_type"],
                "data": encoded,
                "encoding": "base64",
            }
        
        # Handle file paths
        if isinstance(payload, str):
            path = Path(payload.replace("file://", ""))
            if path.exists() and path.is_file():
                try:
                    with path.open("rb") as f:
                        data = f.read()
                    encoded = base64.b64encode(data).decode("ascii")
                    return {
                        "__multimodal__": True,
                        "mime_type": content_info["mime_type"],
                        "content_type": content_info["content_type"],
                        "data": encoded,
                        "encoding": "base64",
                        "source_path": str(path),
                    }
                except (OSError, PermissionError) as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to read file {path} for multimodal encoding: {e}")
                    return payload  # Return original on failure
        
        return payload

    def _write_nbmf_core(self, item_id: str, cls: str, payload: Any, meta: Dict[str, Any]) -> Dict[str, Any]:
        meta = meta or {}
        start_wall = perf_counter()
        start_cpu = process_time()
        
        # Detect and encode multimodal content
        content_info = self._detect_content_type(payload)
        if content_info.get("is_binary"):
            payload = self._encode_multimodal(payload, content_info)
            meta["content_type"] = content_info["content_type"]
            meta["mime_type"] = content_info["mime_type"]
            meta["multimodal"] = True
        
        # Trace NBMF write operation
        if TRACING_AVAILABLE:
            trace_nbmf_operation("write", item_id, cls, "l2")
        
        txid = self.l2.put_record(item_id, cls, payload, meta)
        
        # Track both wall-clock and CPU time
        wall_time = perf_counter() - start_wall
        cpu_time = process_time() - start_cpu
        observe("nbmf_write", wall_time)
        observe_cpu_time("nbmf_write", cpu_time)
        incr("nbmf_writes")
        incr_operation("encode", 1)
        
        self._index_payload(item_id, payload, cls)
        log_event(
            action="write",
            ref=item_id,
            store="nbmf",
            route="primary",
            extra={
                "cls": cls,
                "tenant": meta.get("tenant_id"),
                "compression": meta.get("compression", {}).get("profile"),
                "encrypted": True,  # L2 uses write_secure_json
            },
        )
        
        # Knowledge distillation pipeline: Trust → Quarantine → Distill → Approve → Publish
        if DISTILLATION_AVAILABLE and meta.get("tenant_id") and meta.get("tenant_id") != "default":
            self._process_distillation(item_id, cls, payload, meta)
        
        # OCR comparison integration (if enabled and image detected)
        if self.enable_ocr_comparison and self.ocr_comparison:
            content_info = self._detect_content_type(payload)
            if content_info.get("is_image") and content_info.get("file_path"):
                try:
                    # Store source URI for later comparison
                    meta["source_uri"] = f"file://{content_info['file_path']}"
                    meta["ocr_comparison_enabled"] = True
                except Exception as e:
                    logger.warning(f"OCR comparison setup failed: {e}")
        
        return {"status": "ok", "txid": txid}

    # ------------------------------------------------------------------
    # Write paths
    # ------------------------------------------------------------------
    def write(
        self,
        item_id: str,
        cls: str,
        payload: Any,
        emotion_meta: Optional[Dict[str, Any]] = None,
        policy_ctx: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Write with tenant isolation enforcement.
        
        CRITICAL: Prefixes item_id with tenant_id if provided to ensure isolation.
        """
        meta = dict(emotion_meta or {})
        tenant = self._apply_compression_policy(cls, meta, policy_ctx)
        context = self._policy_context(meta, policy_ctx)
        self.policy.require("write", cls, context)
        
        # CRITICAL: Enforce tenant isolation by prefixing item_id
        if tenant and tenant != "default" and not item_id.startswith(f"{tenant}:"):
            item_id = f"{tenant}:{item_id}"
        
        existing_full = self.l2.get_full_record(item_id, cls, tenant_id=tenant)
        if existing_full:
            self._evaluate_divergence(item_id, cls, payload, existing_full, meta)
        stores: List[str] = []
        if not self._nbmf_primary() or self._flags.dual_write:
            self._legacy.write(item_id, payload, cls, meta)
            incr("legacy_writes")
            log_event(action="write", ref=item_id, store="legacy", route="fallback", extra={"cls": cls, "tenant": tenant})
            stores.append("legacy")
        nbmf_result = self._write_nbmf_core(item_id, cls, payload, meta)
        stores.append("nbmf")
        return {"status": "ok", "stores": stores, "txid": nbmf_result.get("txid")}

    def write_nbmf_only(
        self,
        item_id: str,
        cls: str,
        payload: Any,
        meta: Optional[Dict[str, Any]] = None,
        policy_ctx: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        meta_dict = dict(meta or {})
        tenant = self._apply_compression_policy(cls, meta_dict, policy_ctx)
        context = self._policy_context(meta_dict, policy_ctx)
        self.policy.require("write", cls, context)
        existing_full = self.l2.get_full_record(item_id, cls)
        if existing_full:
            self._evaluate_divergence(item_id, cls, payload, existing_full, meta_dict)
        if not self._nbmf_primary() and self._flags.dual_write:
            self._legacy.write(item_id, payload, cls, meta_dict)
            incr("legacy_writes")
            log_event(action="write", ref=item_id, store="legacy", route="dual-write", extra={"cls": cls, "tenant": tenant})
        return self._write_nbmf_core(item_id, cls, payload, meta_dict)

    def legacy_write(self, item_id: str, cls: str, payload: Any) -> None:
        if self._nbmf_primary():
            raise RuntimeError("Legacy write disabled after NBMF cutover")
        self._legacy.write(item_id, payload, cls)

    # ------------------------------------------------------------------
    # Read paths
    # ------------------------------------------------------------------
    def read(
        self,
        item_id: str,
        cls: str,
        tenant: Optional[str] = None,
        policy_ctx: Optional[Dict[str, Any]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        # Enforce tenant isolation: prefix item_id with tenant_id if provided
        tenant_id = tenant or (meta.get("tenant_id") if meta else None) or (policy_ctx.get("tenant_id") if policy_ctx else None)
        if tenant_id and tenant_id != "default" and not item_id.startswith(f"{tenant_id}:"):
            item_id = f"{tenant_id}:{item_id}"
        
        use_nbmf = self._nbmf_primary() or self._should_use_nbmf(tenant_id)
        context = self._policy_context(meta, policy_ctx)
        self.policy.require("read", cls, context)
        if use_nbmf:
            nbmf_val = self.read_nbmf_only(item_id, cls, policy_ctx=context)
            if nbmf_val is not None:
                return nbmf_val
        if self._flags.legacy_read_through:
            legacy_val = self._legacy.read(item_id)
            if legacy_val is not None:
                incr("legacy_reads")
                if self._nbmf_primary() and not self.l2.exists(item_id, cls):
                    self._write_nbmf_core(item_id, cls, legacy_val, {})
                return legacy_val
        return self.read_nbmf_only(item_id, cls, policy_ctx=context)

    def read_nbmf_only(
        self,
        item_id: str,
        cls: str,
        policy_ctx: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        """Read with graceful degradation and automatic L1→L2 promotion.
        
        CRITICAL: Tenant isolation enforced via item_id prefix (tenant_id:item_id).
        This method assumes item_id already contains tenant prefix if needed.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Extract tenant_id from item_id if present (format: tenant_id:item_id)
        tenant_id = None
        if ":" in item_id:
            parts = item_id.split(":", 1)
            if len(parts) == 2:
                tenant_id, actual_item_id = parts
                # Verify tenant_id matches policy_ctx if provided
                if policy_ctx and policy_ctx.get("tenant_id") and policy_ctx.get("tenant_id") != tenant_id:
                    logger.warning(f"Tenant mismatch: item_id has {tenant_id}, policy_ctx has {policy_ctx.get('tenant_id')}")
                    return None  # SECURITY: Reject cross-tenant access
                item_id = actual_item_id  # Use actual item_id for lookup
        
        # Trace NBMF read operation
        if TRACING_AVAILABLE:
            trace_nbmf_operation("read", item_id, cls, "l2")
        
        try:
            self.policy.require("read", cls, policy_ctx)
        except Exception as e:
            logger.warning(f"Policy check failed for {item_id}:{cls}: {e}")
            # Graceful degradation: allow read if policy check fails (may be transient)
            pass
        
        start_wall = perf_counter()
        start_cpu = process_time()
        
        # Try L2 first (primary storage) - item_id already has tenant prefix if needed
        # Pass tenant_id for additional verification (SECURITY: prevents cross-tenant access)
        try:
            full = self.l2.get_full_record(item_id, cls, tenant_id=tenant_id)
            if full is not None:
                wall_time = perf_counter() - start_wall
                cpu_time = process_time() - start_cpu
                observe("nbmf_read", wall_time)
                observe_cpu_time("nbmf_read", cpu_time)
                incr("nbmf_reads")
                incr_operation("decode", 1)
                
                # Update access metadata for aging/rebalancing
                self._update_access_metadata(item_id, cls, full.get("meta", {}))
                
                # OCR comparison integration (if enabled and image detected)
                if self.enable_ocr_comparison and self.ocr_comparison:
                    meta = full.get("meta", {})
                    source_uri = meta.get("source_uri") or meta.get("lossless_pointer")
                    if source_uri and source_uri.startswith("file://"):
                        image_path = source_uri.replace("file://", "")
                        nbmf_confidence = meta.get("confidence", 1.0)
                        
                        # Use hybrid mode if confidence is low
                        if self.ocr_comparison.should_use_ocr_fallback(nbmf_confidence):
                            try:
                                from pathlib import Path
                                if Path(image_path).exists():
                                    hybrid_result = self.ocr_comparison.hybrid_mode(
                                        image_path=image_path,
                                        nbmf_result={"size_bytes": len(str(full.get("payload", {})).encode('utf-8')), "accuracy": 1.0},
                                        nbmf_confidence=nbmf_confidence
                                    )
                                    meta["ocr_comparison"] = hybrid_result
                                    meta["routing_mode"] = "hybrid_ocr_fallback"
                            except Exception as e:
                                logger.warning(f"OCR comparison failed: {e}")
                
                payload = self._attach_meta(full.get("payload"), full.get("meta", {}))
                log_event(
                    action="read",
                    ref=item_id,
                    store="nbmf",
                    route="primary",
                    extra={"cls": cls, "encrypted": True},
                )
                return payload
        except Exception as e:
            logger.warning(f"L2 read failed for {item_id}:{cls}: {e}, trying L3")
            # Graceful degradation: continue to L3 if L2 fails

        # Try L3 (cold storage)
        try:
            cold = self.l3.get_full_record(item_id, cls)
            if cold is not None:
                # Trace L3 cold read
                if TRACING_AVAILABLE:
                    trace_nbmf_operation("read", item_id, cls, "l3")
                wall_time = perf_counter() - start_wall
                cpu_time = process_time() - start_cpu
                observe("nbmf_read", wall_time)
                observe_cpu_time("nbmf_read", cpu_time)
                incr("nbmf_reads")
                incr_operation("decode", 1)
                
                # Update access metadata
                self._update_access_metadata(item_id, cls, cold.get("meta", {}))
                
                payload = self._attach_meta(cold.get("payload"), cold.get("meta", {}))
                
                # Automatic L3→L2 promotion for frequently accessed items
                meta = cold.get("meta", {})
                access_count = meta.get("access_count", 0)
                if access_count >= 5:  # Promote after 5 accesses
                    try:
                        self.l2.put_record(item_id, cls, cold.get("payload"), meta)
                        logger.info(f"Promoted {item_id}:{cls} from L3 to L2 (access_count={access_count})")
                        
                        # Record DNA lineage for promotion
                        tenant_id = meta.get("tenant_id", "default")
                        try:
                            from memory_service.dna_integration import hook_l3_to_l2_promotion
                            # Get previous lineage hash if available
                            previous_lineage_hash = meta.get("dna_lineage_hash")
                            lineage_hash = hook_l3_to_l2_promotion(
                                item_id=item_id,
                                cls=cls,
                                tenant_id=tenant_id,
                                nbmf_ledger_txid=txid if 'txid' in locals() else "",
                                previous_lineage_hash=previous_lineage_hash,
                                promoted_by="system",
                                metadata={"access_count": access_count, "promotion_reason": "frequent_access"}
                            )
                            if lineage_hash:
                                meta["dna_lineage_hash"] = lineage_hash
                        except ImportError:
                            pass  # DNA service not available
                        
                        log_event(
                            action="promote_l3_to_l2",
                            ref=item_id,
                            store="nbmf",
                            route="aging",
                            extra={"cls": cls, "access_count": access_count},
                        )
                    except Exception as e:
                        logger.warning(f"Failed to promote {item_id}:{cls} to L2: {e}")
                
                self._index_payload(item_id, payload, cls)
                log_event(
                    action="read",
                    ref=item_id,
                    store="nbmf",
                    route="cold",
                    extra={"cls": cls, "encrypted": True},
                )
                return payload
        except Exception as e:
            logger.warning(f"L3 read failed for {item_id}:{cls}: {e}")
            # Graceful degradation: return None if all tiers fail
        
        # Try L1 (vector search) as last resort
        try:
            # Check if item exists in L1 but not in L2/L3 (promote to L2)
            l1_meta = self.l1.meta(item_id) if hasattr(self.l1, 'meta') else None
            if l1_meta:
                # Item exists in L1, promote to L2 for faster access
                try:
                    # Get payload from L1 (if available)
                    l1_payload = self.l1.get(item_id) if hasattr(self.l1, 'get') else None
                    if l1_payload:
                        meta = {"cls": cls, "promoted_from": "l1", "access_count": 1}
                        self.l2.put_record(item_id, cls, l1_payload, meta)
                        logger.info(f"Promoted {item_id}:{cls} from L1 to L2")
                        log_event(
                            action="promote_l1_to_l2",
                            ref=item_id,
                            store="nbmf",
                            route="aging",
                            extra={"cls": cls},
                        )
                        return self._attach_meta(l1_payload, meta)
                except Exception as e:
                    logger.warning(f"Failed to promote {item_id}:{cls} from L1 to L2: {e}")
        except Exception as e:
            logger.debug(f"L1 check failed for {item_id}:{cls}: {e}")
        
        return None

    def recall(
        self,
        query: str,
        k: int = 8,
        policy_ctx: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        start = perf_counter()
        keys = self.l1.search(query, top_k=k)
        observe("l1_search", perf_counter() - start)
        if keys:
            incr("l1_hits", len(keys))
        for key in keys:
            meta = self.l1.meta(key)
            cls = meta.get("cls", "*")
            full = self.l2.get_full_record(key, cls)
            payload = None
            if full is not None:
                payload = self._attach_meta(full.get("payload"), full.get("meta", {}))
            elif self._flags.legacy_read_through:
                legacy_val = self._legacy.read(key)
                if legacy_val is not None:
                    payload = legacy_val
            if payload is not None:
                self.policy.require("read", cls, policy_ctx)
                results.append({"key": key, "payload": payload, "cls": cls})
        return results

    def recall_nbmf_only(
        self,
        query: str,
        k: int = 8,
        policy_ctx: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        start = perf_counter()
        keys = self.l1.search(query, top_k=k)
        observe("l1_search", perf_counter() - start)
        if keys:
            incr("l1_hits", len(keys))
        for key in keys:
            meta = self.l1.meta(key)
            cls = meta.get("cls", "*")
            full = self.l2.get_full_record(key, cls) or self.l3.get_full_record(key, cls)
            if full is not None:
                self.policy.require("read", cls, policy_ctx)
                payload = self._attach_meta(full.get("payload"), full.get("meta", {}))
                out.append({"key": key, "payload": payload, "cls": cls})
        return out

    def store_raw_artifact(self, payload: Any) -> str:
        start = perf_counter()
        key = self.l3.put_json_artifact(payload)
        observe("nbmf_write", perf_counter() - start)
        log_event(action="write", ref=f"artifact:{key}", store="nbmf", route="archive", extra={"cls": "artifact"})
        return key

    # ------------------------------------------------------------------
    # Legacy helpers for migration
    # ------------------------------------------------------------------
    @property
    def legacy_store(self) -> LegacyStore:
        return self._legacy

    def read_legacy(self, item_id: str, cls: str) -> Optional[Any]:
        return self._legacy.read(item_id)

