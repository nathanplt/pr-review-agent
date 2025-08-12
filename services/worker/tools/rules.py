import re
from typing import List, Dict, Any


def analyze(files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Analyze files for potential issues and violations."""
    findings = []
    
    # Compile regex patterns for better performance
    secret = re.compile(r'(?i)(api[_-]?key|aws[_-](secret|access)|password)')
    debugp = re.compile(r'(\bprint\(|console\.log\()')
    
    for f in files:
        path = f.get("filename", "")
        patch = f.get("patch") or ""
        
        for i, line in enumerate(patch.splitlines(), 1):
            if line.startswith("+"):
                txt = line[1:]
                if secret.search(txt):
                    findings.append({
                        "rule_id": "secret",
                        "severity": "high",
                        "reason": "Possible secret in added code",
                        "path": path,
                        "line": i
                    })
                elif debugp.search(txt):
                    findings.append({
                        "rule_id": "debug-print",
                        "severity": "low",
                        "reason": "Debug print/log added",
                        "path": path,
                        "line": i
                    })
        
        # Check for lockfile changes
        if (path.endswith("lock") or path.endswith("lock.json") or 
            path.endswith("lock.yaml") or path.endswith("lock.yml")):
            findings.append({
                "rule_id": "lockfile-changed",
                "severity": "medium",
                "reason": "Lockfile updated; ensure reproducible builds",
                "path": path,
                "line": None
            })
        
        # Check for workflow changes
        if path.startswith(".github/workflows/"):
            findings.append({
                "rule_id": "workflow-edit",
                "severity": "medium",
                "reason": "CI workflow changed; ensure safety",
                "path": path,
                "line": None
            })
    
    return findings


def risk_score(findings: List[Dict[str, Any]]) -> float:
    """Calculate risk score based on findings severity."""
    weights = {"low": 0.5, "medium": 1.0, "high": 2.0}
    return min(
        sum(weights.get(f["severity"], 0.5) for f in findings),
        5.0
    )
