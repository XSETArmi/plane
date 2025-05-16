from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import secrets
import datetime
import requests
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
# Конфигурация API для получения курсов
CRYPTO_API_URL = "https://api.coingecko.com/api/v3"
DEFAULT_CURRENCY = "usd"


# База данных (в реальном приложении используйте SQLAlchemy или другую СУБД)
users_db = {}
wallets_db = {}
transactions_db = {}


class CryptoWallet:
    def __init__(self):
        self.assets = {
            'BTC': {'name': 'Bitcoin', 'balance': 0.0},
            'ETH': {'name': 'Ethereum', 'balance': 0.0},
            'USDT': {'name': 'Tether', 'balance': 0.0}
        }
        self.transactions = []
        self.generate_demo_data()

    def generate_demo_data(self):
        self.assets['BTC']['balance'] = 0.042
        self.assets['ETH']['balance'] = 1.2
        self.assets['USDT']['balance'] = 500

        self.add_transaction('received', 'BTC', 0.01, '1A1zP1...')
        self.add_transaction('sent', 'ETH', 0.5, '0x4bbe...')
        self.add_transaction('exchange', 'USDT', 100, 'Обмен на BTC')

    def add_transaction(self, tx_type, asset, amount, address):
        tx = {
            'type': tx_type,
            'asset': asset,
            'amount': amount,
            'address': address,
            'date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
            'status': 'completed'
        }
        self.transactions.insert(0, tx)

    def get_total_balance(self, rates):
        total = 0.0
        for symbol, asset in self.assets.items():
            rate = rates.get(symbol.lower(), 0)
            total += asset['balance'] * rate
        return round(total, 2)


@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    wallet = wallets_db.get(user_id)

    if not wallet:
        return redirect(url_for('logout'))

    # Получаем текущие курсы
    rates = get_crypto_rates()

    return render_template('index.html',
                           wallet=wallet,
                           rates=rates,
                           total_balance=wallet.get_total_balance(rates))


@app.route('/api/crypto_history')
def crypto_history():
    crypto_id = request.args.get('id', 'bitcoin')
    days = request.args.get('days', '30')

    try:
        response = requests.get(
            f"{CRYPTO_API_URL}/coins/{crypto_id}/market_chart",
            params={
                'vs_currency': DEFAULT_CURRENCY,
                'days': days
            }
        )
        response.raise_for_status()
        return jsonify(response.json())
    except requests.RequestException as e:
        return jsonify({'error': str(e)}), 500

def get_crypto_rates():
    try:
        response = requests.get(
            f"{CRYPTO_API_URL}/simple/price",
            params={
                'ids': 'bitcoin,ethereum,tether',
                'vs_currencies': DEFAULT_CURRENCY
            }
        )
        response.raise_for_status()
        data = response.json()
        return {
            'btc': data['bitcoin'][DEFAULT_CURRENCY],
            'eth': data['ethereum'][DEFAULT_CURRENCY],
            'usdt': data['tether'][DEFAULT_CURRENCY]
        }
    except requests.RequestException:
        # Возвращаем демо-данные если API не доступно
        return {
            'btc': 50000,
            'eth': 3000,
            'usdt': 1
        }

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            return render_template('login.html', error="Заполните все поля")

        user = users_db.get(email)
        if not user or not check_password_hash(user['password'], password):
            return render_template('login.html', error="Неверный email или пароль")

        session['user_id'] = email
        wallets_db[email] = wallets_db.get(email, CryptoWallet())
        return redirect(url_for('index'))

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not email or not password or not confirm_password:
            return render_template('register.html', error="Заполните все поля")

        if password != confirm_password:
            return render_template('register.html', error="Пароли не совпадают")

        if len(password) < 6:
            return render_template('register.html', error="Пароль должен содержать минимум 6 символов")

        if email in users_db:
            return render_template('register.html', error="Пользователь с таким email уже существует")

        users_db[email] = {
            'email': email,
            'password': generate_password_hash(password),
            'created_at': datetime.datetime.now()
        }

        session['user_id'] = email
        wallets_db[email] = CryptoWallet()
        return redirect(url_for('index'))

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))


@app.route('/send', methods=['POST'])
def send_currency():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Необходима авторизация'})

    user_id = session['user_id']
    wallet = wallets_db.get(user_id)

    if not wallet:
        return jsonify({'success': False, 'error': 'Кошелек не найден'})

    asset = request.form.get('asset')
    amount = float(request.form.get('amount'))
    address = request.form.get('address')

    success, message = wallet.send_currency(asset, amount, address)
    return jsonify({'success': success, 'message': message})


@app.route('/receive', methods=['POST'])
def get_address():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Необходима авторизация'})

    user_id = session['user_id']
    wallet = wallets_db.get(user_id)

    if not wallet:
        return jsonify({'success': False, 'error': 'Кошелек не найден'})

    asset = request.form.get('asset')
    address = wallet.generate_address(asset)
    return jsonify({'success': True, 'address': address})


if __name__ == '__main__':
    app.run(debug=True)