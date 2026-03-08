# bad_code.py
def d(x, y):
    # this function does something
    res = 0
    for i in range(x):
        res += y
    return res

class user_manager:
    def __init__(self):
        self.d = {}
        
    def a(self, n, a, e):
        self.d[n] = [a, e]
        print("User added")
        
    def delete(self, n):
        if n in self.d:
            del self.d[n]