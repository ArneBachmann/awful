def fib(n):
  p, q, f = 0, 1, 0
  if n <= 1: return n
  while n >= 2: p, q, n = q, p + q, n - 1
  return q

print([fib(i) for i in range(7)])
print(fib(20))
print(fib(300))
print(fib(1000))
print(fib(10000))
