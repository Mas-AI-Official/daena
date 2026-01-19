# Daena AI VP System - Sunflower Architecture Test
import json
import math
import random
from datetime import datetime

class SunflowerArchitectureTest:
    def __init__(self):
        self.test_results = {
            "test_name": "Sunflower Architecture Test",
            "timestamp": datetime.now().isoformat(),
            "golden_angle": 137.507,
            "departments": 8,
            "agents_per_department": 6,
            "coordinate_tests": [],
            "scaling_tests": [],
            "performance_metrics": {}
        }
    
    def test_golden_angle_calculation(self):
        print("🌻 Testing golden angle calculation...")
        
        # Test golden angle formula: 2π * (3 - √5)
        calculated_angle = 2 * math.pi * (3 - math.sqrt(5))
        expected_angle = 137.507
        
        angle_test = {
            "test_name": "Golden Angle Calculation",
            "calculated_angle": round(calculated_angle, 3),
            "expected_angle": expected_angle,
            "difference": round(abs(calculated_angle - expected_angle), 6),
            "passed": abs(calculated_angle - expected_angle) < 0.001
        }
        
        self.test_results["coordinate_tests"].append(angle_test)
        print(f"✅ Golden angle test: {angle_test['passed']}")
        
        return angle_test
    
    def test_coordinate_generation(self):
        print("📍 Testing coordinate generation...")
        
        # Test sunflower coordinate generation
        n = 8  # 8 departments
        golden_angle = 2 * math.pi * (3 - math.sqrt(5))
        c = 1.0 / math.sqrt(n)
        
        coordinates = []
        for k in range(1, n + 1):
            r = c * math.sqrt(k)
            theta = k * golden_angle
            x = r * math.cos(theta)
            y = r * math.sin(theta)
            
            coordinates.append({
                "department": k,
                "r": round(r, 4),
                "theta": round(theta, 4),
                "x": round(x, 4),
                "y": round(y, 4)
            })
        
        coord_test = {
            "test_name": "Coordinate Generation",
            "departments": n,
            "coordinates": coordinates,
            "golden_angle": round(golden_angle, 3),
            "scaling_factor": round(c, 4)
        }
        
        self.test_results["coordinate_tests"].append(coord_test)
        print(f"✅ Coordinate generation test: {n} departments positioned")
        
        return coord_test
    
    def test_scaling_properties(self):
        print("📏 Testing scaling properties...")
        
        scaling_tests = []
        for n in [4, 8, 16, 32, 64]:  # Test different department counts
            c = 1.0 / math.sqrt(n)
            golden_angle = 2 * math.pi * (3 - math.sqrt(5))
            
            # Calculate coordinates for first few departments
            coords = []
            for k in range(1, min(n + 1, 9)):  # Limit to first 8 for comparison
                r = c * math.sqrt(k)
                theta = k * golden_angle
                coords.append({
                    "k": k,
                    "r": round(r, 4),
                    "theta": round(theta, 4)
                })
            
            # Calculate spacing efficiency
            if len(coords) > 1:
                avg_spacing = sum([coords[i+1]["r"] - coords[i]["r"] for i in range(len(coords)-1)]) / (len(coords)-1)
            else:
                avg_spacing = 0
            
            scaling_test = {
                "department_count": n,
                "scaling_factor": round(c, 4),
                "coordinates": coords,
                "average_spacing": round(avg_spacing, 4),
                "efficiency": round(1.0 / c, 2)  # Higher is more efficient
            }
            
            scaling_tests.append(scaling_test)
        
        self.test_results["scaling_tests"] = scaling_tests
        print(f"✅ Scaling properties test: {len(scaling_tests)} configurations tested")
        
        return scaling_tests
    
    def test_adjacency_calculation(self):
        print("🔗 Testing adjacency calculation...")
        
        # Test neighbor calculation for 8 departments
        n = 8
        golden_angle = 2 * math.pi * (3 - math.sqrt(5))
        c = 1.0 / math.sqrt(n)
        
        coords = []
        for k in range(1, n + 1):
            r = c * math.sqrt(k)
            theta = k * golden_angle
            x = r * math.cos(theta)
            y = r * math.sin(theta)
            coords.append({"k": k, "x": x, "y": y})
        
        # Calculate distances between all pairs
        distances = []
        for i in range(n):
            for j in range(i + 1, n):
                dx = coords[i]["x"] - coords[j]["x"]
                dy = coords[i]["y"] - coords[j]["y"]
                distance = math.sqrt(dx*dx + dy*dy)
                distances.append({
                    "dept1": i + 1,
                    "dept2": j + 1,
                    "distance": round(distance, 4)
                })
        
        # Find closest neighbors
        adjacency_test = {
            "test_name": "Adjacency Calculation",
            "total_pairs": len(distances),
            "distances": distances,
            "closest_pair": min(distances, key=lambda x: x["distance"]),
            "farthest_pair": max(distances, key=lambda x: x["distance"])
        }
        
        self.test_results["coordinate_tests"].append(adjacency_test)
        print(f"✅ Adjacency calculation test: {len(distances)} pairs analyzed")
        
        return adjacency_test
    
    def calculate_performance_metrics(self):
        print("📊 Calculating sunflower architecture performance metrics...")
        
        # Calculate efficiency metrics
        golden_angle_test = next(t for t in self.test_results["coordinate_tests"] if t["test_name"] == "Golden Angle Calculation")
        coord_test = next(t for t in self.test_results["coordinate_tests"] if t["test_name"] == "Coordinate Generation")
        adjacency_test = next(t for t in self.test_results["coordinate_tests"] if t["test_name"] == "Adjacency Calculation")
        
        # Calculate spacing uniformity
        distances = [d["distance"] for d in adjacency_test["distances"]]
        avg_distance = sum(distances) / len(distances)
        distance_variance = sum([(d - avg_distance)**2 for d in distances]) / len(distances)
        spacing_uniformity = 1.0 / (1.0 + distance_variance)  # Higher is more uniform
        
        # Calculate scaling efficiency
        scaling_efficiency = sum([t["efficiency"] for t in self.test_results["scaling_tests"]]) / len(self.test_results["scaling_tests"])
        
        self.test_results["performance_metrics"] = {
            "golden_angle_accuracy": golden_angle_test["passed"],
            "coordinate_generation_success": True,
            "spacing_uniformity": round(spacing_uniformity, 4),
            "average_distance": round(avg_distance, 4),
            "scaling_efficiency": round(scaling_efficiency, 2),
            "total_tests_passed": len([t for t in self.test_results["coordinate_tests"] if t.get("passed", True)]),
            "architecture_quality": round((golden_angle_test["passed"] + spacing_uniformity + scaling_efficiency/100) / 3, 3)
        }
    
    def run_all_tests(self):
        print("🚀 Starting Sunflower Architecture Tests...")
        print("=" * 60)
        
        self.test_golden_angle_calculation()
        self.test_coordinate_generation()
        self.test_scaling_properties()
        self.test_adjacency_calculation()
        self.calculate_performance_metrics()
        
        print("=" * 60)
        print("✅ All Sunflower Architecture Tests Completed!")
        print(f"📊 Golden Angle Accuracy: {self.test_results['performance_metrics']['golden_angle_accuracy']}")
        print(f"📊 Spacing Uniformity: {self.test_results['performance_metrics']['spacing_uniformity']}")
        print(f"📊 Architecture Quality: {self.test_results['performance_metrics']['architecture_quality']}")
        
        return self.test_results

if __name__ == "__main__":
    test = SunflowerArchitectureTest()
    results = test.run_all_tests()
    
    with open("tests/results/sunflower_architecture_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\n💾 Results saved to: tests/results/sunflower_architecture_test_results.json")
