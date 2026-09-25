from werkzeug.security import generate_password_hash, check_password_hash

p = "same-password"

h1 = generate_password_hash(p)
h2 = generate_password_hash(p)

print("h1:", h1)
print("h2:", h2)
print("Are h1 and h2 equal as strings?", h1 == h2)
print("Does h1 verify p?", check_password_hash(h1, p))
print("Does h2 verify p?", check_password_hash(h2, p))