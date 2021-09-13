
import time

### Verifiable Delay Function ###

def Eval(x, t, p):
    x = x % p
    for i in range(t):
        x = mod_sqrt(x, p)
    return x

def Verify(y, x, t, p):
    print(x)
    if not quad_res(x, p):
        x = (-x) % p
    print(x)
    for i in range(t):
        y = pow(int(y), 2, p)
    if x == y:
        return True
    else:
        return False

### Helper Functions ###

def mod_sqrt(x, p):
    #if quad_res(x, p):
    #    pass
    #else:
    y = pow(x, (p + 1) // 4, p)
    return y

def quad_res(x, p):
    return pow(x, (p - 1) // 2, p) == 1

### Main Function ###

def main():
    # Find more primes 256 bit, 512 bit and 1024 bit. They need to be p = 3 mod 4
    p = 73237431696005972674723595250817150843
    t = 10000 # 1.5 sec +/-
    #x = 80 % p

    #p = 1000000007
    #t = 20000
    x = 50 % p

    print('Setup')
    print("Prime validation: "+str(p % 4 == 3))
    print('p =', p)
    print('t =', t)
    print('x =', x)
    print()

    print('Proof generation started...')
    start = time.time()
    y = Eval(x, t, p)
    print('y =', y)
    end = time.time()
    print('Proof generation took: ', format(end - start, '.3f'), 'seconds')
    print()

    print('Proof verification started...')
    start = time.time()
    print('Proof verification result: ', Verify(y, x, t, p))
    end = time.time()
    print('Proof verification took: ', format(end - start,'.3f'), 'seconds')
    print()

if __name__ == "__main__":
    main()
