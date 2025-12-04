from flask import Flask,render_template,request

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('base.html')

@app.route('/index')
def index_page():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        # Add your authentication logic here
        print(f"Login attempt: {username}")
        # For now, just redirect back to home
        return render_template('base.html')
    return render_template('AdminLogin.html')

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)