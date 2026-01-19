"""
Deep System Audit Script
Analyzes the entire Daena system architecture by scanning actual code files
"""

import os
import re
from pathlib import Path
from collections import defaultdict
import json


class DaenaSystemAuditor:
    def __init__(self, root_dir):
        self.root_dir = Path(root_dir)
        self.backend_routes = []
        self.frontend_templates = []
        self.frontend_js = []
        self.route_to_template_map = defaultdict(list)
        self.js_to_api_map = defaultdict(list)
        self.broken_wires = []
        
    def scan_backend_routes(self):
        """Scan all backend route files and extract API endpoints"""
        routes_dir = self.root_dir / "backend" / "routes"
        route_files = list(routes_dir.glob("*.py"))
        
        print(f"\n🔍 Scanning {len(route_files)} backend route files...")
        
        for route_file in route_files:
            if route_file.name == "__init__.py" or route_file.name.startswith("_"):
                continue
                
            try:
                content = route_file.read_text(encoding='utf-8')
                
                # Extract router prefix
                router_prefix_match = re.search(r'router\s*=\s*APIRouter\([^)]*prefix=["\']([^"\']+)', content)
                prefix = router_prefix_match.group(1) if router_prefix_match else ""
                
                # Extract all GET/POST/PUT/DELETE endpoints
                endpoint_pattern = r'@router\.(get|post|put|delete|patch)\(["\']([^"\']+)'
                endpoints = re.findall(endpoint_pattern, content)
                
                # Extract templates rendered
                template_pattern = r'TemplateResponse\(["\']([^"\']+\.html)'
                templates = re.findall(template_pattern, content)
                
                route_info = {
                    'file': route_file.name,
                    'prefix': prefix,
                    'endpoints': [(method.upper(), endpoint) for method, endpoint in endpoints],
                    'templates': list(set(templates)),
                    'size': route_file.stat().st_size
                }
                
                self.backend_routes.append(route_info)
                
                # Map routes to templates
                for template in templates:
                    self.route_to_template_map[template].append({
                        'route_file': route_file.name,
                        'endpoints': route_info['endpoints']
                    })
                    
            except Exception as e:
                print(f"  ⚠️ Error reading {route_file.name}: {e}")
    
    def scan_frontend_templates(self):
        """Scan all frontend template files"""
        templates_dir = self.root_dir / "frontend" / "templates"
        template_files = list(templates_dir.glob("*.html"))
        
        print(f"\n🔍 Scanning {len(template_files)} frontend templates...")
        
        for template_file in template_files:
            try:
                content = template_file.read_text(encoding='utf-8')
                
                # Extract script sources
                script_pattern = r'<script\s+src=["\']([^"\']+\.js)'
                scripts = re.findall(script_pattern, content)
                
                # Extract API calls in inline scripts
                fetch_pattern = r'fetch\(["\']([^"\']+)'
                api_calls = re.findall(fetch_pattern, content)
                
                template_info = {
                    'file': template_file.name,
                    'scripts': list(set(scripts)),
                    'api_calls': list(set(api_calls)),
                    'size': template_file.stat().st_size
                }
                
                self.frontend_templates.append(template_info)
                
            except Exception as e:
                print(f"  ⚠️ Error reading {template_file.name}: {e}")
    
    def scan_javascript_files(self):
        """Scan all JavaScript files for API calls"""
        js_dir = self.root_dir / "frontend" / "static" / "js"
        js_files = list(js_dir.glob("*.js"))
        
        print(f"\n🔍 Scanning {len(js_files)} JavaScript files...")
        
        for js_file in js_files:
            try:
                content = js_file.read_text(encoding='utf-8')
                
                # Extract fetch() calls
                fetch_pattern = r'fetch\(["\']([^"\']+)'
                fetch_calls = re.findall(fetch_pattern, content)
                
                # Extract axios calls
                axios_pattern = r'axios\.(get|post|put|delete|patch)\(["\']([^"\']+)'
                axios_calls = [(method.upper(), url) for method, url in re.findall(axios_pattern, content)]
                
                all_api_calls = list(set(fetch_calls + [url for _, url in axios_calls]))
                
                js_info = {
                    'file': js_file.name,
                    'api_calls': all_api_calls,
                    'size': js_file.stat().st_size
                }
                
                self.frontend_js.append(js_info)
                
                # Map JS to APIs
                for api_call in all_api_calls:
                    self.js_to_api_map[api_call].append(js_file.name)
                    
            except Exception as e:
                print(f"  ⚠️ Error reading {js_file.name}: {e}")
    
    def verify_route_template_wiring(self):
        """Verify that all templates referenced in routes exist"""
        print("\n🔌 Verifying route → template wiring...")
        
        existing_templates = {t['file'] for t in self.frontend_templates}
        
        for route in self.backend_routes:
            for template in route['templates']:
                if template not in existing_templates:
                    self.broken_wires.append({
                        'type': 'missing_template',
                        'route_file': route['file'],
                        'missing_template': template
                    })
    
    def verify_api_endpoints(self):
        """Verify that frontend API calls match backend endpoints"""
        print("\n🔌 Verifying frontend → backend API wiring...")
        
        # Build set of all backend endpoints
        backend_endpoints = set()
        for route in self.backend_routes:
            prefix = route['prefix']
            for method, endpoint in route['endpoints']:
                full_endpoint = prefix + endpoint if not endpoint.startswith('/') else endpoint
                backend_endpoints.add(full_endpoint)
        
        # Check frontend API calls
        all_frontend_calls = set()
        for js in self.frontend_js:
            all_frontend_calls.update(js['api_calls'])
        for template in self.frontend_templates:
            all_frontend_calls.update(template['api_calls'])
        
        # Find broken wires
        for api_call in all_frontend_calls:
            #  Extract the endpoint path (remove query params)
            clean_endpoint = api_call.split('?')[0]
            
            # Check if it's a backend API call
            if clean_endpoint.startswith('/api/') or clean_endpoint.startswith('/health'):
                if not any(clean_endpoint.startswith(ep.split('?')[0]) for ep in backend_endpoints):
                    # Check for dynamic routes (e.g., /api/users/{id})
                    is_dynamic = False
                    for backend_ep in backend_endpoints:
                        # Convert {param} to regex pattern
                        pattern = re.sub(r'\{[^}]+\}', '[^/]+', backend_ep)
                        if re.match(pattern, clean_endpoint):
                            is_dynamic = True
                            break
                    
                    if not is_dynamic:
                        self.broken_wires.append({
                            'type': 'missing_backend_endpoint',
                            'frontend_call': api_call,
                            'sources': self.js_to_api_map.get(api_call, [])
                        })
    
    def generate_report(self):
        """Generate comprehensive audit report"""
        report = {
            'summary': {
                'backend_routes': len(self.backend_routes),
                'frontend_templates': len(self.frontend_templates),
                'javascript_files': len(self.frontend_js),
                'total_backend_endpoints': sum(len(r['endpoints']) for r in self.backend_routes),
                'broken_wires': len(self.broken_wires)
            },
            'backend_routes': self.backend_routes,
            'frontend_templates': self.frontend_templates,
            'frontend_js': self.frontend_js,
            'route_to_template_map': dict(self.route_to_template_map),
            'js_to_api_map': dict(self.js_to_api_map),
            'broken_wires': self.broken_wires
        }
        
        return report
    
    def print_summary(self):
        """Print human-readable summary"""
        print("\n" + "="*80)
        print("📊 DAENA SYSTEM AUDIT SUMMARY")
        print("="*80)
        
        print(f"\n📁 Backend:")
        print(f"  • {len(self.backend_routes)} route files")
        print(f"  • {sum(len(r['endpoints']) for r in self.backend_routes)} total API endpoints")
        
        print(f"\n🌐 Frontend:")
        print(f"  • {len(self.frontend_templates)} HTML templates")
        print(f"  • {len(self.frontend_js)} JavaScript files")
        
        if self.broken_wires:
            print(f"\n⚠️  Found {len(self.broken_wires)} broken wires:")
            for wire in self.broken_wires[:10]:  # Show first 10
                if wire['type'] == 'missing_template':
                    print(f"  • {wire['route_file']} references missing template: {wire['missing_template']}")
                elif wire['type'] == 'missing_backend_endpoint':
                    print(f"  • Frontend calls missing endpoint: {wire['frontend_call']}")
                    print(f"    Sources: {', '.join(wire['sources'][:3])}")
        else:
            print("\n✅ No broken wires found!")
        
        print("\n📈 Top 10 Largest Route Files:")
        sorted_routes = sorted(self.backend_routes, key=lambda x: x['size'], reverse=True)[:10]
        for route in sorted_routes:
            print(f"  • {route['file']}: {route['size']:,} bytes ({len(route['endpoints'])} endpoints)")
        
        print("\n🔗 Route → Template Mappings:")
        for template, routes in list(self.route_to_template_map.items())[:10]:
            print(f"  • {template}")
            for route in routes[:2]:
                print(f"    ← {route['route_file']}")
    
    def run_full_audit(self):
        """Run complete system audit"""
        print("🚀 Starting Deep System Audit...")
        print(f"📍 Root Directory: {self.root_dir}")
        
        self.scan_backend_routes()
        self.scan_frontend_templates()
        self.scan_javascript_files()
        self.verify_route_template_wiring()
        self.verify_api_endpoints()
        
        report = self.generate_report()
        self.print_summary()
        
        # Save detailed report
        report_path = self.root_dir / "system_audit_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: {report_path}")
        
        return report


if __name__ == "__main__":
    root_dir = r"D:\Ideas\Daena_old_upgrade_20251213"
    auditor = DaenaSystemAuditor(root_dir)
    report = auditor.run_full_audit()
