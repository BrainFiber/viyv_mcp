"""Example Python file for Claude Code CLI testing"""

def fibonacci(n):
    """Generate Fibonacci sequence up to n terms"""
    if n <= 0:
        return []
    elif n == 1:
        return [0]
    elif n == 2:
        return [0, 1]
    
    fib_seq = [0, 1]
    for i in range(2, n):
        fib_seq.append(fib_seq[i-1] + fib_seq[i-2])
    
    return fib_seq

def main():
    # Test the fibonacci function
    print("Fibonacci sequence (first 10 terms):")
    print(fibonacci(10))
    
    # Example tasks for Claude:
    # 1. Add error handling
    # 2. Create unit tests
    # 3. Add type hints
    # 4. Optimize for large numbers

if __name__ == "__main__":
    main()