"""Security Tool Catalog -- Daena's knowledge of every tool in the arsenal.

When the OODA loop needs a capability, it checks this catalog:
    1. What tools can do this?
    2. Are they installed?
    3. If not, how do I install them?
    4. What are the right flags for this use case?

This is the "equip yourself" pattern: Daena doesn't just think, she
acquires the tools she needs to execute her thinking.

BACKGROUND PATH ONLY -- never import in hot path
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SecurityTool:
    """A security tool Daena knows about."""
    name: str
    category: str           # recon, scanning, exploitation, post-exploit, osint, etc.
    description: str        # What it does in one line
    capabilities: list[str] # What tasks it can perform
    install_cmd: str        # How to install on current OS
    check_cmd: str          # Command to verify it's installed (binary name or path)
    usage_examples: list[dict[str, str]] = field(default_factory=list)
    offensive_only: bool = False  # Requires /3vilbob?
    platforms: list[str] = field(default_factory=lambda: ["linux", "windows", "macos"])
    url: str = ""           # Project homepage


# ---------------------------------------------------------------------------
# The Catalog (comprehensive -- 80+ tools)
# ---------------------------------------------------------------------------

_CATALOG: list[SecurityTool] = [
    # ===== RECONNAISSANCE =====
    SecurityTool(
        name="subfinder",
        category="recon",
        description="Fast passive subdomain discovery using multiple sources",
        capabilities=["subdomain_enumeration", "passive_recon", "dns_recon"],
        install_cmd="go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest",
        check_cmd="subfinder",
        usage_examples=[
            {"task": "find subdomains", "cmd": "subfinder -d {target} -silent"},
            {"task": "all sources", "cmd": "subfinder -d {target} -all -o subs.txt"},
        ],
        url="https://github.com/projectdiscovery/subfinder",
    ),
    SecurityTool(
        name="amass",
        category="recon",
        description="In-depth attack surface mapping and asset discovery",
        capabilities=["subdomain_enumeration", "dns_recon", "network_mapping", "asset_discovery"],
        install_cmd="go install -v github.com/owasp-amass/amass/v4/...@master",
        check_cmd="amass",
        usage_examples=[
            {"task": "passive enum", "cmd": "amass enum -passive -d {target}"},
            {"task": "active enum", "cmd": "amass enum -d {target} -active"},
        ],
        url="https://github.com/owasp-amass/amass",
    ),
    SecurityTool(
        name="httpx",
        category="recon",
        description="Fast HTTP probing and technology fingerprinting",
        capabilities=["http_probing", "tech_detection", "status_codes", "web_server_detection"],
        install_cmd="go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest",
        check_cmd="httpx",
        usage_examples=[
            {"task": "probe hosts", "cmd": "cat hosts.txt | httpx -silent -status-code -tech-detect"},
            {"task": "title + tech", "cmd": "httpx -u {target} -title -tech-detect -status-code"},
        ],
        url="https://github.com/projectdiscovery/httpx",
    ),
    SecurityTool(
        name="dnsx",
        category="recon",
        description="Fast DNS toolkit for record queries and wildcard detection",
        capabilities=["dns_recon", "dns_bruteforce", "wildcard_detection"],
        install_cmd="go install -v github.com/projectdiscovery/dnsx/cmd/dnsx@latest",
        check_cmd="dnsx",
        usage_examples=[
            {"task": "resolve", "cmd": "echo {target} | dnsx -resp -a -aaaa -cname -mx"},
        ],
        url="https://github.com/projectdiscovery/dnsx",
    ),
    SecurityTool(
        name="naabu",
        category="recon",
        description="Fast port scanner with SYN/CONNECT scan support",
        capabilities=["port_scanning", "service_detection"],
        install_cmd="go install -v github.com/projectdiscovery/naabu/v2/cmd/naabu@latest",
        check_cmd="naabu",
        usage_examples=[
            {"task": "top ports", "cmd": "naabu -host {target} -top-ports 1000"},
            {"task": "full scan", "cmd": "naabu -host {target} -p - -silent"},
        ],
        url="https://github.com/projectdiscovery/naabu",
    ),
    SecurityTool(
        name="nmap",
        category="recon",
        description="Network exploration and security auditing (the gold standard)",
        capabilities=["port_scanning", "service_detection", "os_fingerprinting", "script_scanning", "network_mapping"],
        install_cmd="choco install nmap -y" if os.name == "nt" else "sudo apt-get install -y nmap",
        check_cmd="nmap",
        usage_examples=[
            {"task": "service detection", "cmd": "nmap -sV -sC {target}"},
            {"task": "aggressive scan", "cmd": "nmap -A -T4 {target}"},
            {"task": "stealth SYN", "cmd": "nmap -sS -T2 {target}"},
            {"task": "vuln scripts", "cmd": "nmap --script vuln {target}"},
        ],
        url="https://nmap.org",
    ),
    SecurityTool(
        name="masscan",
        category="recon",
        description="Internet-scale port scanner (fastest port scanner)",
        capabilities=["port_scanning", "mass_scanning"],
        install_cmd="sudo apt-get install -y masscan",
        check_cmd="masscan",
        usage_examples=[
            {"task": "fast scan", "cmd": "masscan {target}/24 -p1-65535 --rate=10000"},
        ],
        url="https://github.com/robertdavidgraham/masscan",
    ),
    SecurityTool(
        name="shodan",
        category="recon",
        description="Search engine for Internet-connected devices",
        capabilities=["passive_recon", "service_detection", "iot_scanning", "banner_grabbing"],
        install_cmd="pip install shodan",
        check_cmd="shodan",
        usage_examples=[
            {"task": "host info", "cmd": "shodan host {target}"},
            {"task": "search", "cmd": "shodan search 'hostname:{target}'"},
        ],
        url="https://www.shodan.io",
    ),
    SecurityTool(
        name="censys",
        category="recon",
        description="Internet-wide scanning and certificate transparency",
        capabilities=["passive_recon", "certificate_transparency", "service_detection"],
        install_cmd="pip install censys",
        check_cmd="censys",
        usage_examples=[
            {"task": "search hosts", "cmd": "censys search '{target}'"},
        ],
        url="https://censys.io",
    ),

    # ===== VULNERABILITY SCANNING =====
    SecurityTool(
        name="nuclei",
        category="scanning",
        description="Fast template-based vulnerability scanner (10K+ templates)",
        capabilities=["vulnerability_scanning", "cve_detection", "misconfig_detection", "exposure_detection"],
        install_cmd="go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest",
        check_cmd="nuclei",
        usage_examples=[
            {"task": "full scan", "cmd": "nuclei -u {target} -as"},
            {"task": "critical only", "cmd": "nuclei -u {target} -severity critical,high"},
            {"task": "specific template", "cmd": "nuclei -u {target} -t cves/"},
            {"task": "headless", "cmd": "nuclei -u {target} -headless"},
        ],
        url="https://github.com/projectdiscovery/nuclei",
    ),
    SecurityTool(
        name="nikto",
        category="scanning",
        description="Web server scanner for dangerous files, outdated software, misconfigs",
        capabilities=["web_scanning", "misconfig_detection", "outdated_software_detection"],
        install_cmd="sudo apt-get install -y nikto",
        check_cmd="nikto",
        usage_examples=[
            {"task": "basic scan", "cmd": "nikto -h {target}"},
            {"task": "with tuning", "cmd": "nikto -h {target} -Tuning 123bde"},
        ],
        url="https://github.com/sullo/nikto",
    ),
    SecurityTool(
        name="wpscan",
        category="scanning",
        description="WordPress security scanner",
        capabilities=["wordpress_scanning", "plugin_detection", "theme_detection", "user_enumeration"],
        install_cmd="gem install wpscan",
        check_cmd="wpscan",
        usage_examples=[
            {"task": "full scan", "cmd": "wpscan --url {target} --enumerate ap,at,u"},
        ],
        url="https://github.com/wpscanteam/wpscan",
    ),
    SecurityTool(
        name="testssl",
        category="scanning",
        description="TLS/SSL cipher, protocol, and cryptographic flaw testing",
        capabilities=["ssl_scanning", "cipher_testing", "certificate_analysis"],
        install_cmd="git clone https://github.com/drwetter/testssl.sh.git",
        check_cmd="testssl.sh",
        usage_examples=[
            {"task": "full test", "cmd": "testssl.sh {target}"},
            {"task": "vulnerabilities", "cmd": "testssl.sh -U {target}"},
        ],
        url="https://github.com/drwetter/testssl.sh",
    ),

    # ===== WEB APPLICATION TESTING =====
    SecurityTool(
        name="katana",
        category="web",
        description="Next-gen web crawler with headless browser support",
        capabilities=["web_crawling", "js_crawling", "endpoint_discovery", "form_discovery"],
        install_cmd="go install github.com/projectdiscovery/katana/cmd/katana@latest",
        check_cmd="katana",
        usage_examples=[
            {"task": "crawl", "cmd": "katana -u {target} -d 3 -jc"},
            {"task": "headless", "cmd": "katana -u {target} -headless -d 5"},
        ],
        url="https://github.com/projectdiscovery/katana",
    ),
    SecurityTool(
        name="ffuf",
        category="web",
        description="Fast web fuzzer for directory/file/parameter discovery",
        capabilities=["directory_bruteforce", "parameter_fuzzing", "vhost_discovery", "content_discovery"],
        install_cmd="go install github.com/ffuf/ffuf/v2@latest",
        check_cmd="ffuf",
        usage_examples=[
            {"task": "dir brute", "cmd": "ffuf -w wordlist.txt -u {target}/FUZZ -mc 200,301,302,403"},
            {"task": "param fuzz", "cmd": "ffuf -w params.txt -u '{target}?FUZZ=test'"},
            {"task": "vhost", "cmd": "ffuf -w vhosts.txt -u {target} -H 'Host: FUZZ.{target}'"},
        ],
        url="https://github.com/ffuf/ffuf",
    ),
    SecurityTool(
        name="feroxbuster",
        category="web",
        description="Fast content discovery tool with recursive scanning",
        capabilities=["directory_bruteforce", "content_discovery", "recursive_scanning"],
        install_cmd="cargo install feroxbuster",
        check_cmd="feroxbuster",
        usage_examples=[
            {"task": "recursive scan", "cmd": "feroxbuster -u {target} -w wordlist.txt --depth 3"},
        ],
        url="https://github.com/epi052/feroxbuster",
    ),
    SecurityTool(
        name="gobuster",
        category="web",
        description="Directory/file and DNS bruteforcing",
        capabilities=["directory_bruteforce", "dns_bruteforce", "vhost_discovery"],
        install_cmd="go install github.com/OJ/gobuster/v3@latest",
        check_cmd="gobuster",
        usage_examples=[
            {"task": "dir mode", "cmd": "gobuster dir -u {target} -w wordlist.txt"},
            {"task": "dns mode", "cmd": "gobuster dns -d {target} -w subdomains.txt"},
        ],
        url="https://github.com/OJ/gobuster",
    ),
    SecurityTool(
        name="dalfox",
        category="web",
        description="XSS scanning and parameter analysis",
        capabilities=["xss_scanning", "parameter_analysis", "reflected_xss", "stored_xss"],
        install_cmd="go install github.com/hahwul/dalfox/v2@latest",
        check_cmd="dalfox",
        usage_examples=[
            {"task": "scan URL", "cmd": "dalfox url '{target}?q=test'"},
            {"task": "pipe mode", "cmd": "cat urls.txt | dalfox pipe"},
        ],
        offensive_only=True,
        url="https://github.com/hahwul/dalfox",
    ),
    SecurityTool(
        name="sqlmap",
        category="web",
        description="Automatic SQL injection detection and exploitation",
        capabilities=["sqli_detection", "sqli_exploitation", "database_enumeration", "data_extraction"],
        install_cmd="pip install sqlmap",
        check_cmd="sqlmap",
        usage_examples=[
            {"task": "test URL", "cmd": "sqlmap -u '{target}?id=1' --batch"},
            {"task": "enumerate DBs", "cmd": "sqlmap -u '{target}?id=1' --dbs --batch"},
            {"task": "dump table", "cmd": "sqlmap -u '{target}?id=1' -D db --tables --batch"},
        ],
        offensive_only=True,
        url="https://github.com/sqlmapproject/sqlmap",
    ),
    SecurityTool(
        name="commix",
        category="web",
        description="Command injection detection and exploitation",
        capabilities=["command_injection", "os_command_exploitation"],
        install_cmd="pip install commix",
        check_cmd="commix",
        usage_examples=[
            {"task": "test", "cmd": "commix --url='{target}?cmd=test' --batch"},
        ],
        offensive_only=True,
        url="https://github.com/commixproject/commix",
    ),
    SecurityTool(
        name="arjun",
        category="web",
        description="HTTP parameter discovery",
        capabilities=["parameter_discovery", "hidden_parameter_detection"],
        install_cmd="pip install arjun",
        check_cmd="arjun",
        usage_examples=[
            {"task": "find params", "cmd": "arjun -u {target}"},
        ],
        url="https://github.com/s0md3v/Arjun",
    ),

    # ===== OSINT =====
    SecurityTool(
        name="theHarvester",
        category="osint",
        description="Email, subdomain, and name harvesting from public sources",
        capabilities=["email_harvesting", "subdomain_enumeration", "people_intel"],
        install_cmd="pip install theHarvester",
        check_cmd="theHarvester",
        usage_examples=[
            {"task": "harvest", "cmd": "theHarvester -d {target} -b all"},
        ],
        url="https://github.com/laramies/theHarvester",
    ),
    SecurityTool(
        name="spiderfoot",
        category="osint",
        description="Automated OSINT collection and correlation",
        capabilities=["osint_automation", "email_harvesting", "social_media_recon", "dark_web_recon"],
        install_cmd="pip install spiderfoot",
        check_cmd="spiderfoot",
        usage_examples=[
            {"task": "scan", "cmd": "spiderfoot -s {target} -o json"},
        ],
        url="https://github.com/smicallef/spiderfoot",
    ),
    SecurityTool(
        name="sherlock",
        category="osint",
        description="Find social media accounts by username across 400+ sites",
        capabilities=["social_media_recon", "username_enumeration"],
        install_cmd="pip install sherlock-project",
        check_cmd="sherlock",
        usage_examples=[
            {"task": "hunt username", "cmd": "sherlock {username}"},
        ],
        url="https://github.com/sherlock-project/sherlock",
    ),
    SecurityTool(
        name="holehe",
        category="osint",
        description="Check if an email is registered on 120+ sites",
        capabilities=["email_osint", "account_discovery"],
        install_cmd="pip install holehe",
        check_cmd="holehe",
        usage_examples=[
            {"task": "check email", "cmd": "holehe {email}"},
        ],
        url="https://github.com/megadose/holehe",
    ),

    # ===== EXPLOITATION =====
    SecurityTool(
        name="metasploit",
        category="exploitation",
        description="World's most used penetration testing framework",
        capabilities=["exploitation", "payload_generation", "post_exploitation", "privilege_escalation"],
        install_cmd="curl https://raw.githubusercontent.com/rapid7/metasploit-omnibus/master/config/templates/metasploit-framework-wrappers/msfupdate.erb > msfinstall && chmod 755 msfinstall && ./msfinstall",
        check_cmd="msfconsole",
        offensive_only=True,
        usage_examples=[
            {"task": "search exploit", "cmd": "msfconsole -q -x 'search type:exploit {target}'"},
        ],
        url="https://github.com/rapid7/metasploit-framework",
    ),
    SecurityTool(
        name="searchsploit",
        category="exploitation",
        description="Offline exploit database search (ExploitDB)",
        capabilities=["exploit_search", "cve_lookup"],
        install_cmd="sudo apt-get install -y exploitdb",
        check_cmd="searchsploit",
        offensive_only=True,
        usage_examples=[
            {"task": "search", "cmd": "searchsploit {software} {version}"},
            {"task": "with CVE", "cmd": "searchsploit --cve {cve_id}"},
        ],
        url="https://gitlab.com/exploit-database/exploitdb",
    ),

    # ===== CREDENTIAL TESTING =====
    SecurityTool(
        name="hydra",
        category="credential",
        description="Fast password brute-forcer supporting 50+ protocols",
        capabilities=["credential_bruteforce", "password_spraying", "service_authentication"],
        install_cmd="sudo apt-get install -y hydra",
        check_cmd="hydra",
        offensive_only=True,
        usage_examples=[
            {"task": "SSH brute", "cmd": "hydra -l admin -P passwords.txt {target} ssh"},
            {"task": "HTTP form", "cmd": "hydra -l admin -P pass.txt {target} http-post-form '/login:user=^USER^&pass=^PASS^:F=incorrect'"},
        ],
        url="https://github.com/vanhauser-thc/thc-hydra",
    ),
    SecurityTool(
        name="hashcat",
        category="credential",
        description="World's fastest password recovery (GPU-accelerated)",
        capabilities=["password_cracking", "hash_identification", "hash_attack"],
        install_cmd="sudo apt-get install -y hashcat",
        check_cmd="hashcat",
        offensive_only=True,
        usage_examples=[
            {"task": "crack MD5", "cmd": "hashcat -m 0 hashes.txt wordlist.txt"},
            {"task": "crack NTLM", "cmd": "hashcat -m 1000 hashes.txt wordlist.txt"},
        ],
        url="https://github.com/hashcat/hashcat",
    ),
    SecurityTool(
        name="john",
        category="credential",
        description="Password cracker (CPU-based, wide format support)",
        capabilities=["password_cracking", "hash_identification"],
        install_cmd="sudo apt-get install -y john",
        check_cmd="john",
        offensive_only=True,
        usage_examples=[
            {"task": "crack", "cmd": "john --wordlist=wordlist.txt hashes.txt"},
        ],
        url="https://github.com/openwall/john",
    ),

    # ===== NETWORK / MITM =====
    SecurityTool(
        name="wireshark",
        category="network",
        description="Network protocol analyzer (GUI + tshark CLI)",
        capabilities=["packet_capture", "protocol_analysis", "traffic_analysis"],
        install_cmd="choco install wireshark -y" if os.name == "nt" else "sudo apt-get install -y wireshark",
        check_cmd="tshark",
        usage_examples=[
            {"task": "capture", "cmd": "tshark -i eth0 -w capture.pcap"},
            {"task": "filter HTTP", "cmd": "tshark -r capture.pcap -Y 'http.request'"},
        ],
        url="https://www.wireshark.org",
    ),
    SecurityTool(
        name="mitmproxy",
        category="network",
        description="Interactive HTTPS proxy for inspecting/modifying traffic",
        capabilities=["traffic_interception", "request_modification", "ssl_interception"],
        install_cmd="pip install mitmproxy",
        check_cmd="mitmproxy",
        offensive_only=True,
        usage_examples=[
            {"task": "intercept", "cmd": "mitmproxy --mode transparent"},
            {"task": "dump traffic", "cmd": "mitmdump -w traffic.flow"},
        ],
        url="https://mitmproxy.org",
    ),
    SecurityTool(
        name="responder",
        category="network",
        description="LLMNR/NBT-NS/MDNS poisoner for credential capture",
        capabilities=["credential_capture", "ntlm_relay", "network_poisoning"],
        install_cmd="pip install Responder",
        check_cmd="responder",
        offensive_only=True,
        usage_examples=[
            {"task": "poison", "cmd": "responder -I eth0 -dwPv"},
        ],
        url="https://github.com/lgandx/Responder",
    ),

    # ===== CLOUD SECURITY =====
    SecurityTool(
        name="cloudfox",
        category="cloud",
        description="AWS/Azure/GCP enumeration for pentesters",
        capabilities=["cloud_enumeration", "iam_analysis", "privilege_escalation_paths"],
        install_cmd="go install github.com/BishopFox/cloudfox@latest",
        check_cmd="cloudfox",
        usage_examples=[
            {"task": "AWS enum", "cmd": "cloudfox aws --profile {profile} all-checks"},
        ],
        url="https://github.com/BishopFox/cloudfox",
    ),
    SecurityTool(
        name="prowler",
        category="cloud",
        description="AWS/Azure/GCP security assessment and compliance",
        capabilities=["cloud_audit", "compliance_checking", "misconfig_detection"],
        install_cmd="pip install prowler",
        check_cmd="prowler",
        usage_examples=[
            {"task": "AWS audit", "cmd": "prowler aws"},
            {"task": "GCP audit", "cmd": "prowler gcp"},
        ],
        url="https://github.com/prowler-cloud/prowler",
    ),
    SecurityTool(
        name="scoutsuite",
        category="cloud",
        description="Multi-cloud security auditing (AWS, Azure, GCP, OCI)",
        capabilities=["cloud_audit", "misconfig_detection", "iam_analysis"],
        install_cmd="pip install scoutsuite",
        check_cmd="scout",
        usage_examples=[
            {"task": "AWS audit", "cmd": "scout aws"},
        ],
        url="https://github.com/nccgroup/ScoutSuite",
    ),
    SecurityTool(
        name="trufflehog",
        category="cloud",
        description="Find leaked credentials in git repos, S3, filesystems",
        capabilities=["secret_scanning", "credential_detection", "git_scanning"],
        install_cmd="pip install trufflehog",
        check_cmd="trufflehog",
        usage_examples=[
            {"task": "scan repo", "cmd": "trufflehog git {repo_url}"},
            {"task": "scan fs", "cmd": "trufflehog filesystem {path}"},
        ],
        url="https://github.com/trufflesecurity/trufflehog",
    ),
    SecurityTool(
        name="gitleaks",
        category="cloud",
        description="Secret detection in git repos (fast, regex-based)",
        capabilities=["secret_scanning", "git_scanning"],
        install_cmd="go install github.com/gitleaks/gitleaks/v8@latest",
        check_cmd="gitleaks",
        usage_examples=[
            {"task": "detect", "cmd": "gitleaks detect --source={path}"},
        ],
        url="https://github.com/gitleaks/gitleaks",
    ),

    # ===== CONTAINER / K8S =====
    SecurityTool(
        name="trivy",
        category="container",
        description="Container/filesystem/repo vulnerability scanner",
        capabilities=["container_scanning", "filesystem_scanning", "sbom_generation"],
        install_cmd="curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh",
        check_cmd="trivy",
        usage_examples=[
            {"task": "scan image", "cmd": "trivy image {image}"},
            {"task": "scan fs", "cmd": "trivy fs ."},
        ],
        url="https://github.com/aquasecurity/trivy",
    ),
    SecurityTool(
        name="grype",
        category="container",
        description="Vulnerability scanner for container images and filesystems",
        capabilities=["container_scanning", "sbom_scanning"],
        install_cmd="curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sh",
        check_cmd="grype",
        usage_examples=[
            {"task": "scan", "cmd": "grype {image}"},
        ],
        url="https://github.com/anchore/grype",
    ),

    # ===== MOBILE =====
    SecurityTool(
        name="mobsf",
        category="mobile",
        description="Mobile Security Framework (Android/iOS static + dynamic analysis)",
        capabilities=["mobile_scanning", "apk_analysis", "ipa_analysis"],
        install_cmd="pip install mobsf",
        check_cmd="mobsf",
        usage_examples=[
            {"task": "analyze APK", "cmd": "mobsf -i app.apk"},
        ],
        url="https://github.com/MobSF/Mobile-Security-Framework-MobSF",
    ),

    # ===== WORDLISTS =====
    SecurityTool(
        name="seclists",
        category="wordlists",
        description="Collection of wordlists for fuzzing and bruteforcing",
        capabilities=["wordlist_provider"],
        install_cmd="git clone https://github.com/danielmiessler/SecLists.git /opt/seclists",
        check_cmd="ls /opt/seclists/Discovery 2>/dev/null || ls ~/seclists/Discovery 2>/dev/null",
        usage_examples=[
            {"task": "common dirs", "cmd": "/opt/seclists/Discovery/Web-Content/common.txt"},
            {"task": "passwords", "cmd": "/opt/seclists/Passwords/Common-Credentials/10k-most-common.txt"},
        ],
        url="https://github.com/danielmiessler/SecLists",
    ),

    # ===== PROXY / ANONYMITY =====
    SecurityTool(
        name="tor",
        category="anonymity",
        description="Anonymous network for scanning without revealing source IP",
        capabilities=["anonymity", "ip_rotation"],
        install_cmd="choco install tor -y" if os.name == "nt" else "sudo apt-get install -y tor",
        check_cmd="tor",
        usage_examples=[
            {"task": "start", "cmd": "tor --SocksPort 9050"},
            {"task": "use with curl", "cmd": "curl --socks5 127.0.0.1:9050 {target}"},
        ],
        url="https://www.torproject.org",
    ),
    SecurityTool(
        name="proxychains",
        category="anonymity",
        description="Route any TCP connection through proxy chains",
        capabilities=["anonymity", "proxy_chaining"],
        install_cmd="sudo apt-get install -y proxychains4",
        check_cmd="proxychains4",
        usage_examples=[
            {"task": "use with nmap", "cmd": "proxychains4 nmap -sT {target}"},
        ],
        url="https://github.com/haad/proxychains",
    ),

    # ===== API SECURITY =====
    SecurityTool(
        name="kiterunner",
        category="api",
        description="API endpoint discovery via wordlists and swagger",
        capabilities=["api_discovery", "endpoint_enumeration"],
        install_cmd="go install github.com/assetnote/kiterunner/cmd/kr@latest",
        check_cmd="kr",
        usage_examples=[
            {"task": "scan", "cmd": "kr scan {target} -w routes-large.kite"},
        ],
        url="https://github.com/assetnote/kiterunner",
    ),
    SecurityTool(
        name="postman",
        category="api",
        description="API testing platform (also has CLI: newman)",
        capabilities=["api_testing", "request_crafting"],
        install_cmd="npm install -g newman",
        check_cmd="newman",
        usage_examples=[
            {"task": "run collection", "cmd": "newman run collection.json"},
        ],
        url="https://www.postman.com",
    ),

    # ===== BROWSER AUTOMATION =====
    SecurityTool(
        name="playwright",
        category="browser",
        description="Browser automation for headless testing and evidence capture",
        capabilities=["browser_automation", "screenshot_capture", "dom_interaction", "js_execution"],
        install_cmd="pip install playwright && playwright install",
        check_cmd="playwright",
        usage_examples=[
            {"task": "screenshot", "cmd": "playwright screenshot {target} --full-page"},
        ],
        url="https://playwright.dev",
    ),

    # ===== REPORTING =====
    SecurityTool(
        name="sn1per",
        category="automation",
        description="Automated pentest recon framework",
        capabilities=["automated_recon", "vulnerability_scanning", "osint_automation"],
        install_cmd="git clone https://github.com/1N3/Sn1per.git && cd Sn1per && bash install.sh",
        check_cmd="sniper",
        offensive_only=True,
        usage_examples=[
            {"task": "full scan", "cmd": "sniper -t {target}"},
        ],
        url="https://github.com/1N3/Sn1per",
    ),
]


# ---------------------------------------------------------------------------
# Catalog API
# ---------------------------------------------------------------------------

class ToolCatalog:
    """Daena's tool knowledge base.

    Query by capability, check installation, auto-install.
    """

    def __init__(self) -> None:
        self._tools: dict[str, SecurityTool] = {t.name: t for t in _CATALOG}
        self._capability_index: dict[str, list[str]] = {}
        self._build_index()

    def _build_index(self) -> None:
        """Build capability -> tool name index."""
        for tool in _CATALOG:
            for cap in tool.capabilities:
                self._capability_index.setdefault(cap, []).append(tool.name)

    # ------ Query ------

    def find_by_capability(self, capability: str) -> list[SecurityTool]:
        """Find tools that provide a specific capability."""
        names = self._capability_index.get(capability, [])
        return [self._tools[n] for n in names if n in self._tools]

    def find_by_category(self, category: str) -> list[SecurityTool]:
        """Find tools in a category (recon, scanning, web, osint, etc.)."""
        return [t for t in _CATALOG if t.category == category]

    def search(self, query: str) -> list[SecurityTool]:
        """Fuzzy search tools by name, description, or capability."""
        q = query.lower()
        results = []
        for tool in _CATALOG:
            score = 0
            if q in tool.name.lower():
                score += 10
            if q in tool.description.lower():
                score += 5
            if any(q in cap.lower() for cap in tool.capabilities):
                score += 3
            if q in tool.category.lower():
                score += 2
            if score > 0:
                results.append((score, tool))
        results.sort(key=lambda x: -x[0])
        return [t for _, t in results]

    def get_all(self) -> list[SecurityTool]:
        """Return all known tools."""
        return list(_CATALOG)

    def get(self, name: str) -> SecurityTool | None:
        """Get a specific tool by name."""
        return self._tools.get(name)

    # ------ Installation checks ------

    def is_installed(self, name: str) -> bool:
        """Check if a tool is installed on the current system."""
        tool = self._tools.get(name)
        if not tool:
            return False
        return shutil.which(tool.check_cmd) is not None

    def get_installed(self) -> list[SecurityTool]:
        """Return all tools currently installed."""
        return [t for t in _CATALOG if self.is_installed(t.name)]

    def get_missing(self) -> list[SecurityTool]:
        """Return all tools NOT currently installed."""
        return [t for t in _CATALOG if not self.is_installed(t.name)]

    def get_install_plan(self, capability: str) -> list[dict[str, str]]:
        """Get install commands for tools that provide a capability but aren't installed."""
        tools = self.find_by_capability(capability)
        missing = [t for t in tools if not self.is_installed(t.name)]
        return [{"name": t.name, "install_cmd": t.install_cmd} for t in missing]

    # ------ Auto-install ------

    async def auto_install(self, name: str) -> dict[str, Any]:
        """Auto-install a tool. Returns success status and output.

        NOTE: This runs a subprocess. Only call from background path.
        """
        tool = self._tools.get(name)
        if not tool:
            return {"success": False, "error": f"Unknown tool: {name}"}

        if self.is_installed(name):
            return {"success": True, "already_installed": True}

        logger.info("tool_catalog.installing", tool=name, cmd=tool.install_cmd)

        try:
            # tool.install_cmd is a hardcoded string literal defined in
            # _DEFAULT_TOOLS above; never derived from user input. shell=True
            # is needed so multi-step chains like
            # ``choco install X -y && npm install Y`` work. Bandit B602
            # is therefore a false positive at this site.
            result = subprocess.run(  # nosec B602
                tool.install_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,
            )
            success = result.returncode == 0
            if success:
                logger.info("tool_catalog.installed", tool=name)
            else:
                logger.warning(
                    "tool_catalog.install_failed",
                    tool=name,
                    stderr=result.stderr[:500],
                )
            return {
                "success": success,
                "stdout": result.stdout[:1000],
                "stderr": result.stderr[:1000],
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Install timed out (300s)"}
        except Exception as exc:
            return {"success": False, "error": str(exc)[:500]}

    # ------ Usage ------

    def get_usage(self, name: str, task: str) -> str | None:
        """Get the best usage example for a tool and task.

        Args:
            name: Tool name
            task: What you want to do (e.g., "find subdomains", "scan ports")

        Returns:
            Command template string or None
        """
        tool = self._tools.get(name)
        if not tool:
            return None

        task_lower = task.lower()
        for example in tool.usage_examples:
            if any(word in example["task"].lower() for word in task_lower.split()):
                return example["cmd"]

        # Return first example if no match
        if tool.usage_examples:
            return tool.usage_examples[0]["cmd"]
        return None

    def recommend_for_target(
        self,
        target_type: str,
        waf_detected: str = "",
        technologies: list[str] | None = None,
    ) -> list[SecurityTool]:
        """Recommend tools based on target characteristics.

        The OODA loop calls this in DECIDE phase to select the right arsenal.
        """
        technologies = technologies or []
        recommended: list[SecurityTool] = []
        seen: set[str] = set()

        def _add(tools: list[SecurityTool]) -> None:
            for t in tools:
                if t.name not in seen:
                    recommended.append(t)
                    seen.add(t.name)

        # Always: recon tools
        _add(self.find_by_capability("subdomain_enumeration")[:2])
        _add(self.find_by_capability("port_scanning")[:2])
        _add(self.find_by_capability("http_probing")[:1])

        # WAF detected: need stealth tools
        if waf_detected:
            _add(self.find_by_capability("anonymity"))

        # Web target: web tools
        if target_type in ("web_application", "api_only", "startup"):
            _add(self.find_by_capability("web_crawling")[:1])
            _add(self.find_by_capability("directory_bruteforce")[:1])
            _add(self.find_by_capability("vulnerability_scanning")[:1])
            _add(self.find_by_capability("parameter_discovery")[:1])

        # API detected
        if "api" in target_type or any("api" in t.lower() for t in technologies):
            _add(self.find_by_capability("api_discovery"))

        # WordPress
        if any("wordpress" in t.lower() for t in technologies):
            _add(self.find_by_capability("wordpress_scanning"))

        # Cloud
        if target_type in ("cloud_service", "hardened_cloud"):
            _add(self.find_by_capability("cloud_enumeration")[:1])
            _add(self.find_by_capability("secret_scanning")[:1])

        # Container
        if any(t.lower() in ("docker", "kubernetes", "k8s") for t in technologies):
            _add(self.find_by_capability("container_scanning")[:1])

        return recommended

    # ------ Stats ------

    @property
    def total_tools(self) -> int:
        return len(_CATALOG)

    @property
    def total_capabilities(self) -> int:
        return len(self._capability_index)

    @property
    def categories(self) -> list[str]:
        return sorted({t.category for t in _CATALOG})
