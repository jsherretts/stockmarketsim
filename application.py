import os
import datetime

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# export API_KEY=pk_e816316e1dbf40a592892987d147a145
# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


#Gives the homepage, where users can access the overall value of holdings of their portfolio
@app.route("/")
@login_required
def index():
    rows = db.execute("SELECT symbol, SUM(shares) AS shares FROM transactions WHERE user_id = :id GROUP BY symbol", id = session["user_id"])
    # stock = {}
    grandTotal = 0
    for stock in rows:
        info = lookup(stock["symbol"])
        # stock["stock"] = info["symbol"]
        stock["totalShares"] = int(stock["shares"])
        stock["price"] = usd(info["price"])
        stock["name"] = info["name"]
        stock["totalPrice"] = usd(stock["totalShares"] * info["price"])
        grandTotal += stock["totalShares"] * info["price"]
    rows2 = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
    cash = rows2[0]["cash"]
    return render_template("index.html", rows = rows, cash = usd(cash), grandTotal = usd(grandTotal + cash))

#Gives users the option to add cash, if they decide they want to invest more
@app.route("/addcash", methods=["GET", "POST"])
@login_required
def addcash():
    if request.method == "GET":
        return render_template("addcash.html")
    else:
        addCash = int(request.form.get("addcash"))
        rows = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
        totalCash = rows[0]["cash"] + addCash
        if totalCash < 0:
            return render_template("apology.html", message = "You do not have enough money to perform this action.")
        else:
            rows = db.execute("UPDATE users SET cash = :totalCash WHERE id = :id", totalCash = totalCash, id = session["user_id"])
            # rows = db.execute("INSERT INTO transactions (user_id, symbol, shares, price, time, type) VALUES (?,?,?,?,?,?)", session["user_id"], "N/A", 0, addCash, datetime.datetime.now(), "ADD CASH")
        return redirect("/")


#allows users to buy stock by calling the API to access the real-time price of the searched stock and subtracting the equivalent value from cash and adding stocks to portfolio
#transaction is denied if user does not have enough cash
@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return render_template("buy.html")
    else:
        symbol = request.form.get("stock")
        quantity = request.form.get("quantity")
        if not symbol:
            return render_template("apology.html", message = "You must enter a stock.")
        if not quantity:
            return render_template("apology.html", message = "You must enter a quantity of stock to buy.")
        stock = lookup(symbol)
        if not stock:
            return render_template("apology.html", message = "That stock does not exist.")
        price = stock["price"]
        totalPrice = price * int(quantity)
        rows = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
        totalCash = rows[0]["cash"] - totalPrice
        if totalCash < 0:
            return render_template("apology.html", message = "You do not have enough cash to make this transaction.")
        else:
            rows = db.execute("UPDATE users SET cash = :totalCash WHERE id = :id", totalCash = totalCash, id = session["user_id"])
            rows = db.execute("INSERT INTO transactions (user_id, symbol, shares, price, time, type) VALUES (?,?,?,?,?,?)", session["user_id"], symbol, quantity, price, datetime.datetime.now(), "BUY")
        return redirect("/")
        # return render_template("quoted.html", stock = session.user_id, price = session.user_id)
    # """Buy shares of stock"""
    # return apology("TODO")


#accesses the SQL database history of past transactions
@app.route("/history")
@login_required
def history():
    rows = db.execute("SELECT symbol, shares, price, time, type FROM transactions WHERE user_id = :id", id = session["user_id"])
    for stock in rows:
        if stock["type"] == "SELL":
            stock["shares"] = -1 * stock["shares"]
        info = lookup(stock["symbol"])
        stock["totalPrice"] = usd(stock["shares"] * int(stock["price"]))
        stock["name"] = info["name"]

    return render_template("history.html", rows = rows)



@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


#returns the price of any current stock seached
@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")
        if not symbol:
            return render_template("apology.html", message = "You must enter a stock.")
        stock = lookup(symbol)
        if not stock:
            return render_template("apology.html", message = "That stock does not exist.")
        return render_template("quoted.html", stock = stock, price = usd(stock["price"]))
        # if stock == "None":
        #     return render_template("apology.html", message = "That stock does not exist")


    # """Get stock quote."""
    # return apology("TODO")


#allows users to register for a new account/portfolio
#password is secured with a hash
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    else:
        username = request.form.get("username")

        if not username:
            return render_template("apology.html", message = "You must provide a username.")
        password = request.form.get("password")
        confirmation = request.form.get("confirm")

        if password != confirmation:
            return render_template("apology.html", message = "Your passwords must match.")
        hash = generate_password_hash(request.form.get("password"))

        if not hash:
            return render_template("apology.html", message = "You must provide a password.")

        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))
        if len(rows) == 1:
            return render_template("apology.html", message = "This username has already been taken.")

        db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username = username, hash = hash)
        return redirect("/login")
    # """Register user"""
    # return apology("TODO")


#allows users to sell stock by calling the API to access the real-time price of the searched stock and adding the equivalent value from cash and subtracting stocks to portfolio
#transaction is denied if user does not have enough stock
@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "GET":
        return render_template("sell.html")
    else:
        symbol = request.form.get("stock")
        quantity = request.form.get("quantity")
        if not symbol:
            return render_template("apology.html", message = "You must enter a stock.")
        if not quantity:
            return render_template("apology.html", message = "You must enter a quantity of stock to buy.")
        stock = lookup(symbol)
        if not stock:
            return render_template("apology.html", message = "That stock does not exist.")
        price = stock["price"]
        totalPrice = price * int(quantity)
        rows = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
        rows2 = db.execute("SELECT symbol, SUM(shares) AS shares FROM transactions WHERE user_id = :id GROUP BY symbol HAVING symbol = :symbol", id = session["user_id"], symbol = symbol)
        totalCash = rows[0]["cash"] + totalPrice
        totalQuantity = rows2[0]["shares"]
        inverseQuantity = -1 * int(quantity)
        if totalQuantity < int(quantity):
            return render_template("apology.html", message = "You do not have enough of the selected stock to make this transaction.")
        else:
            rows = db.execute("UPDATE users SET cash = :totalCash WHERE id = :id", totalCash = totalCash, id = session["user_id"])
            rows = db.execute("INSERT INTO transactions (user_id, symbol, shares, price, time, type) VALUES (?,?,?,?,?,?)", session["user_id"], symbol, inverseQuantity, price, datetime.datetime.now(), "SELL")
        return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
