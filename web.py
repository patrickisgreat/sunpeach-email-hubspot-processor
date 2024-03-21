from flask import Flask, request
app = Flask(__name__)


@app.route('/')
def oauth_callback():
    authorization_code = request.args.get('code')
    if authorization_code:
        print(f"Authorization code: {authorization_code}")
        # Here, you would proceed with exchanging the authorization code for an access token.
        return "Authorization code received. You can close this window."
    else:
        return "No code provided."


if __name__ == '__main__':
    app.run('localhost', 8080)
