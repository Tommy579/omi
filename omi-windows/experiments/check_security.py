import requests  
import hashlib  
  
def check_password_pwned(password):  
    sha1password = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()  
    prefix = sha1password[:5]  
    suffix = sha1password[5:]  
  
    url = f"https://api.pwnedpasswords.com/range/{prefix}"  
    response = requests.get(url)  
  
    if suffix in response.text:  
        return "?? Attention : ce mot de passe a ‚t‚ compromis !"  
    return "? Ce mot de passe semble s–r." 
  
if __name__ == "__main__":  
    pwd = input("Entrez le mot de passe … v‚rifier : ")  
    print(check_password_pwned(pwd)) 
