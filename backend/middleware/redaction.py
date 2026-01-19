"""PII (Personally Identifiable Information) redaction middleware."""
import re
import logging
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class PIIRedactor:
    """PII detection and redaction engine."""
    
    def __init__(self):
        # Email patterns
        self.email_patterns = [
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            r'\b[A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9.-]+\s*\.\s*[A-Z|a-z]{2,}\b'
        ]
        
        # Phone number patterns (US and international)
        self.phone_patterns = [
            r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',  # US: 123-456-7890
            r'\b\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}\b',  # International
            r'\b\(\d{3}\)\s*\d{3}[-.\s]?\d{4}\b',  # US: (123) 456-7890
            r'\b\d{10,15}\b'  # Long numbers
        ]
        
        # Address patterns
        self.address_patterns = [
            r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Way|Place|Pl)\b',
            r'\b[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Way|Place|Pl)\s+\d+\b',
            r'\b\d{5}(?:-\d{4})?\b',  # ZIP codes
            r'\b[A-Z]{2}\s+\d{5}\b'  # State + ZIP
        ]
        
        # Credit card patterns
        self.credit_patterns = [
            r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',  # 16 digits
            r'\b\d{4}[-\s]?\d{6}[-\s]?\d{5}\b',  # 15 digits (Amex)
            r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{3}\b',  # 15 digits
        ]
        
        # SSN patterns
        self.ssn_patterns = [
            r'\b\d{3}-\d{2}-\d{4}\b',
            r'\b\d{9}\b'
        ]
        
        # IP address patterns
        self.ip_patterns = [
            r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
            r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b'  # IPv6
        ]
        
        # Compile all patterns
        self.all_patterns = {
            'email': [re.compile(pattern, re.IGNORECASE) for pattern in self.email_patterns],
            'phone': [re.compile(pattern) for pattern in self.phone_patterns],
            'address': [re.compile(pattern, re.IGNORECASE) for pattern in self.address_patterns],
            'credit_card': [re.compile(pattern) for pattern in self.credit_patterns],
            'ssn': [re.compile(pattern) for pattern in self.ssn_patterns],
            'ip_address': [re.compile(pattern) for pattern in self.ip_patterns]
        }
        
        # Redaction templates
        self.redaction_templates = {
            'email': '[EMAIL_REDACTED]',
            'phone': '[PHONE_REDACTED]',
            'address': '[ADDRESS_REDACTED]',
            'credit_card': '[CREDIT_CARD_REDACTED]',
            'ssn': '[SSN_REDACTED]',
            'ip_address': '[IP_REDACTED]'
        }
    
    def detect_pii(self, text: str) -> List[Dict[str, Any]]:
        """Detect PII in text and return details."""
        if not isinstance(text, str):
            return []
        
        detected_pii = []
        
        for pii_type, patterns in self.all_patterns.items():
            for pattern in patterns:
                matches = pattern.finditer(text)
                for match in matches:
                    detected_pii.append({
                        'type': pii_type,
                        'value': match.group(),
                        'start': match.start(),
                        'end': match.end(),
                        'confidence': self._calculate_confidence(pii_type, match.group())
                    })
        
        # Sort by start position
        detected_pii.sort(key=lambda x: x['start'])
        
        return detected_pii
    
    def _calculate_confidence(self, pii_type: str, value: str) -> float:
        """Calculate confidence score for PII detection."""
        base_confidence = 0.8
        
        if pii_type == 'email':
            if '@' in value and '.' in value.split('@')[1]:
                return 0.95
            return 0.7
        
        elif pii_type == 'phone':
            digits = re.sub(r'\D', '', value)
            if len(digits) >= 10:
                return 0.9
            return 0.6
        
        elif pii_type == 'credit_card':
            digits = re.sub(r'\D', '', value)
            if len(digits) in [13, 15, 16]:
                return 0.85
            return 0.5
        
        elif pii_type == 'ssn':
            digits = re.sub(r'\D', '', value)
            if len(digits) == 9:
                return 0.9
            return 0.6
        
        return base_confidence
    
    def redact_text(self, text: str, redaction_type: str = 'full') -> Tuple[str, List[Dict[str, Any]]]:
        """Redact PII from text."""
        if not isinstance(text, str):
            return text, []
        
        detected_pii = self.detect_pii(text)
        if not detected_pii:
            return text, []
        
        # Sort by start position (reverse to avoid index shifting)
        detected_pii.sort(key=lambda x: x['start'], reverse=True)
        
        redacted_text = text
        redaction_log = []
        
        for pii in detected_pii:
            start = pii['start']
            end = pii['end']
            original_value = pii['value']
            
            if redaction_type == 'full':
                replacement = self.redaction_templates[pii['type']]
            elif redaction_type == 'partial':
                replacement = self._partial_redact(original_value, pii['type'])
            else:
                replacement = '[REDACTED]'
            
            redacted_text = redacted_text[:start] + replacement + redacted_text[end:]
            
            redaction_log.append({
                'type': pii['type'],
                'original': original_value,
                'replacement': replacement,
                'confidence': pii['confidence'],
                'timestamp': datetime.now().isoformat()
            })
        
        return redacted_text, redaction_log
    
    def _partial_redact(self, value: str, pii_type: str) -> str:
        """Partially redact PII values."""
        if pii_type == 'email':
            parts = value.split('@')
            if len(parts) == 2:
                username = parts[0]
                domain = parts[1]
                if len(username) > 2:
                    redacted_username = username[:2] + '*' * (len(username) - 2)
                else:
                    redacted_username = username
                return f"{redacted_username}@{domain}"
        
        elif pii_type == 'phone':
            digits = re.sub(r'\D', '', value)
            if len(digits) >= 4:
                return f"***-***-{digits[-4:]}"
            return value
        
        elif pii_type == 'credit_card':
            digits = re.sub(r'\D', '', value)
            if len(digits) >= 4:
                return f"{'*' * (len(digits) - 4)}{digits[-4:]}"
            return value
        
        # Default partial redaction
        if len(value) > 4:
            return value[:2] + '*' * (len(value) - 4) + value[-2:]
        return value
    
    def validate_redaction(self, original_text: str, redacted_text: str) -> Dict[str, Any]:
        """Validate that redaction was successful."""
        original_pii = self.detect_pii(original_text)
        redacted_pii = self.detect_pii(redacted_text)
        
        return {
            'original_pii_count': len(original_pii),
            'remaining_pii_count': len(redacted_pii),
            'redaction_success_rate': round(
                (len(original_pii) - len(redacted_pii)) / max(1, len(original_pii)) * 100, 2
            ),
            'remaining_pii_types': list(set(pii['type'] for pii in redacted_pii)),
            'validation_passed': len(redacted_pii) == 0
        }

# Global PII redactor instance
pii_redactor = PIIRedactor()

def redact_pii_middleware(content: Any, redaction_type: str = 'full') -> Tuple[Any, List[Dict[str, Any]]]:
    """Middleware function to redact PII from content."""
    if isinstance(content, str):
        redacted_content, redaction_log = pii_redactor.redact_text(content, redaction_type)
        return redacted_content, redaction_log
    
    elif isinstance(content, dict):
        redacted_content = {}
        all_redaction_logs = []
        
        for key, value in content.items():
            if isinstance(value, str):
                redacted_value, logs = pii_redactor.redact_text(value, redaction_type)
                redacted_content[key] = redacted_value
                all_redaction_logs.extend(logs)
            else:
                redacted_content[key] = value
        
        return redacted_content, all_redaction_logs
    
    elif isinstance(content, list):
        redacted_content = []
        all_redaction_logs = []
        
        for item in content:
            if isinstance(item, str):
                redacted_item, logs = pii_redactor.redact_text(item, redaction_type)
                redacted_content.append(redacted_item)
                all_redaction_logs.extend(logs)
            else:
                redacted_content.append(item)
        
        return redacted_content, all_redaction_logs
    
    else:
        return content, [] 