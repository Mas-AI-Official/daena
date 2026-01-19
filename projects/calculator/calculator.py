"""
Simple Calculator - Created by Daena's Engineering Department
Built via agent collaboration through Daena AI VP system
"""

def add(a: float, b: float) -> float:
    """Add two numbers"""
    return a + b

def subtract(a: float, b: float) -> float:
    """Subtract b from a"""
    return a - b

def multiply(a: float, b: float) -> float:
    """Multiply two numbers"""
    return a * b

def divide(a: float, b: float) -> float:
    """Divide a by b"""
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b

def power(base: float, exponent: float) -> float:
    """Raise base to exponent power"""
    return base ** exponent

def square_root(n: float) -> float:
    """Calculate square root"""
    if n < 0:
        raise ValueError("Cannot calculate square root of negative number")
    return n ** 0.5

def percentage(value: float, percent: float) -> float:
    """Calculate percentage of a value"""
    return value * (percent / 100)


class Calculator:
    """Calculator class with memory function"""
    
    def __init__(self):
        self.memory = 0.0
        self.history = []
    
    def calculate(self, operation: str, a: float, b: float = None) -> float:
        """Perform calculation and store in history"""
        ops = {
            'add': lambda: add(a, b),
            'subtract': lambda: subtract(a, b),
            'multiply': lambda: multiply(a, b),
            'divide': lambda: divide(a, b),
            'power': lambda: power(a, b),
            'sqrt': lambda: square_root(a),
            'percent': lambda: percentage(a, b)
        }
        
        if operation not in ops:
            raise ValueError(f"Unknown operation: {operation}")
        
        result = ops[operation]()
        self.history.append({
            'operation': operation,
            'a': a,
            'b': b,
            'result': result
        })
        return result
    
    def store_memory(self, value: float):
        """Store value in memory"""
        self.memory = value
    
    def recall_memory(self) -> float:
        """Recall value from memory"""
        return self.memory
    
    def clear_memory(self):
        """Clear memory"""
        self.memory = 0.0
    
    def get_history(self) -> list:
        """Get calculation history"""
        return self.history
    
    def clear_history(self):
        """Clear calculation history"""
        self.history = []


# Interactive CLI
def main():
    calc = Calculator()
    print("=" * 50)
    print("   DAENA CALCULATOR - Built by AI Agents")
    print("   Created via Daena AI VP System")
    print("=" * 50)
    print("\nOperations: add, subtract, multiply, divide, power, sqrt, percent")
    print("Commands: memory, recall, clear, history, quit\n")
    
    while True:
        try:
            user_input = input("Enter operation (or 'quit'): ").strip().lower()
            
            if user_input == 'quit':
                print("Thank you for using Daena Calculator!")
                break
            elif user_input == 'history':
                for h in calc.get_history():
                    print(f"  {h['operation']}: {h['a']} {'& ' + str(h['b']) if h['b'] else ''} = {h['result']}")
                continue
            elif user_input == 'recall':
                print(f"Memory: {calc.recall_memory()}")
                continue
            elif user_input == 'clear':
                calc.clear_memory()
                calc.clear_history()
                print("Memory and history cleared.")
                continue
            
            a = float(input("Enter first number: "))
            
            if user_input == 'sqrt':
                result = calc.calculate(user_input, a)
            else:
                b = float(input("Enter second number: "))
                result = calc.calculate(user_input, a, b)
            
            print(f"Result: {result}")
            
            save = input("Store in memory? (y/n): ").strip().lower()
            if save == 'y':
                calc.store_memory(result)
                print("Stored in memory.")
                
        except ValueError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
