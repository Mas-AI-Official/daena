"""
Training Data Collection Script

Collects and prepares training data for NBMF encoder training.

Usage:
    python training/collect_training_data.py --domain general --output data/training/general/
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List

from memory_service.router import MemoryRouter


def collect_from_memory_service(
    router: MemoryRouter,
    domain: str,
    limit: int = 10000
) -> List[Dict[str, Any]]:
    """Collect training samples from existing memory service."""
    samples = []
    
    try:
        # Collect from L2 store
        if hasattr(router.l2, "iter_records"):
            count = 0
            for item_id, cls, record in router.l2.iter_records():
                if count >= limit:
                    break
                
                # Filter by domain/class
                if domain == "general" or cls == domain:
                    payload = record.get("payload")
                    if payload:
                        samples.append({
                            "id": f"{item_id}_{count}",
                            "domain": domain,
                            "type": "text" if isinstance(payload, str) else "structured",
                            "data": payload,
                            "metadata": {
                                "source": "memory_service",
                                "class": cls,
                                "item_id": item_id,
                                "collected_at": time.time()
                            }
                        })
                        count += 1
    except AttributeError:
        # L2Store doesn't have iter_records
        pass
    
    return samples


def collect_from_files(
    data_dir: Path,
    domain: str,
    limit: int = 10000
) -> List[Dict[str, Any]]:
    """Collect training samples from files."""
    samples = []
    
    # Look for JSON files
    json_files = list(data_dir.glob("*.json"))
    for json_file in json_files[:limit]:
        try:
            with open(json_file) as f:
                data = json.load(f)
                samples.append({
                    "id": json_file.stem,
                    "domain": domain,
                    "type": "structured",
                    "data": data,
                    "metadata": {
                        "source": "file",
                        "file": str(json_file),
                        "collected_at": time.time()
                    }
                })
        except Exception as e:
            print(f"Error reading {json_file}: {e}")
    
    # Look for text files
    text_files = list(data_dir.glob("*.txt"))
    for text_file in text_files[:limit]:
        try:
            with open(text_file, encoding="utf-8") as f:
                text = f.read()
                if len(text) > 100:  # Minimum length
                    samples.append({
                        "id": text_file.stem,
                        "domain": domain,
                        "type": "text",
                        "data": text,
                        "metadata": {
                            "source": "file",
                            "file": str(text_file),
                            "collected_at": time.time()
                        }
                    })
        except Exception as e:
            print(f"Error reading {text_file}: {e}")
    
    return samples


def create_training_pairs(
    samples: List[Dict[str, Any]],
    output_dir: Path
) -> None:
    """Create training pairs (original → compressed → reconstructed)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    training_pairs = []
    
    for sample in samples:
        # For now, create placeholder pairs
        # In production, this would use the current encoder to create compressed versions
        pair = {
            "id": sample["id"],
            "domain": sample["domain"],
            "original": sample["data"],
            "compressed": None,  # Will be filled during training
            "reconstructed": None,  # Will be filled during training
            "compression_ratio": None,  # Will be calculated
            "similarity_score": None,  # Will be calculated
            "metadata": sample["metadata"]
        }
        training_pairs.append(pair)
    
    # Save training pairs
    output_file = output_dir / "training_pairs.json"
    with open(output_file, "w") as f:
        json.dump(training_pairs, f, indent=2, ensure_ascii=False)
    
    print(f"Created {len(training_pairs)} training pairs in {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Collect training data for NBMF encoder")
    parser.add_argument("--domain", type=str, default="general", help="Domain (general, financial, legal)")
    parser.add_argument("--output", type=str, default="data/training", help="Output directory")
    parser.add_argument("--limit", type=int, default=10000, help="Maximum samples to collect")
    parser.add_argument("--source", type=str, choices=["memory", "files", "both"], default="both",
                       help="Data source")
    parser.add_argument("--data-dir", type=str, help="Directory with training files")
    
    args = parser.parse_args()
    
    output_dir = Path(args.output) / args.domain
    output_dir.mkdir(parents=True, exist_ok=True)
    
    samples = []
    
    # Collect from memory service
    if args.source in ["memory", "both"]:
        print("Collecting from memory service...")
        router = MemoryRouter()
        memory_samples = collect_from_memory_service(router, args.domain, args.limit)
        samples.extend(memory_samples)
        print(f"Collected {len(memory_samples)} samples from memory service")
    
    # Collect from files
    if args.source in ["files", "both"]:
        if args.data_dir:
            print(f"Collecting from files in {args.data_dir}...")
            data_dir = Path(args.data_dir)
            file_samples = collect_from_files(data_dir, args.domain, args.limit)
            samples.extend(file_samples)
            print(f"Collected {len(file_samples)} samples from files")
        else:
            print("Warning: --data-dir not specified, skipping file collection")
    
    # Create training pairs
    if samples:
        print(f"\nCreating training pairs from {len(samples)} samples...")
        create_training_pairs(samples, output_dir)
        
        # Save raw samples
        samples_file = output_dir / "raw_samples.json"
        with open(samples_file, "w") as f:
            json.dump(samples, f, indent=2, ensure_ascii=False)
        
        print(f"\nSummary:")
        print(f"  Domain: {args.domain}")
        print(f"  Samples collected: {len(samples)}")
        print(f"  Output directory: {output_dir}")
        print(f"  Raw samples: {samples_file}")
        print(f"  Training pairs: {output_dir / 'training_pairs.json'}")
    else:
        print("No samples collected. Check data sources and try again.")


if __name__ == "__main__":
    main()

