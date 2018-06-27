import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Ensure environment variable is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

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


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Gives list of stock table with stocks, their sum of shares and price
    stocks = db.execute("SELECT stock, SUM(shares) as totalshares FROM portfolio WHERE id = :currentid GROUP BY stock", currentid = session["user_id"])

    # Create new keys in each dict in each list element containing the dict
    i = 0
    while (i < len(stocks)):

        # Checks if shares are zero in portfolio table
        if stocks[i]["totalshares"] <= 0:
            del stocks[i]

            if i == 0:
                continue
            else:
                i = i - 1

        # Checks if there are no stocks to show
        elif not stocks:
            return render_template("nostocks.html")

        # Create new keys for currentprice and grandvalue and input corresponding values
        else:
            lookstock = lookup(stocks[i]["stock"])
            stocks[i]["currentprice"] = usd((lookstock["price"]))
            stocks[i]["grandvalue"] = usd(stocks[i]["totalshares"] * (lookstock["price"]))

            # key created solely to calculate grand total, since using usd() gives a string with $ signs, so we can't cast usd() on grandvalue key and so can't do arithmetic
            stocks[i]["grandvaluez"] = stocks[i]["totalshares"] * (lookstock["price"])
            i = i + 1

    # Returns no stock template if there are zero stocks
    if len(stocks) == 0:
        return render_template("nostocks.html")

    # Fetch total cash user has
    user = db.execute("SELECT cash FROM users WHERE id = :currentid", currentid = session["user_id"])
    cash = round(user[0]["cash"])

    # To calculate grand total, initialize grandtotal to cash contained
    grandtotal = cash

    # Adds grand values to calculate grand total
    for j in range(len(stocks)):
        grandtotal += int(float(stocks[j]["grandvaluez"]))

    # return index template
    return render_template("index.html", htmlstocks = stocks, cash = usd(cash), gtotal = usd(grandtotal))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # Check the method, if GET, return form
    if request.method == "GET":
        return render_template("buy.html")

    # Check method, if POST, do stuff
    elif request.method == "POST":

        # Checks if valid stock symbol is submitted
        if not request.form.get("symbol") or lookup(request.form.get("symbol")) == None:
            return apology("Please enter valid stock symbol.")

        # Checks if shares submitted is a positive integer and is a num and contains no decimals
        if not request.form.get("shares").isdigit():
            return apology("Please enter a valid integer.")

        elif not float(request.form.get("shares")) % 1 == 0:
            return apology("Please enter a valid integer.")

        elif int(float(request.form.get("shares"))) < 1:
            return apology("Please enter a valid integer.")

        # Stores stock, shares, cost, cash in variables
        stock = lookup(request.form.get("symbol"))
        shares = int(request.form.get("shares"))
        cost = stock["price"] * shares
        cash = db.execute("SELECT cash FROM users WHERE id = :currentid", currentid = session["user_id"])
        remain = cash[0]["cash"] - cost

        # Checks if user has enough cash
        if cash[0]["cash"] < cost:
            return apology("Not enough cash.")

        elif cash[0]["cash"] > cost:
            result = db.execute("INSERT INTO portfolio (id, stock, shares, price) VALUES(:_id, :_stock, :_shares, :_price)", _id = session["user_id"], _stock = stock["symbol"], _shares = shares, _price = cost)

            if not result:
                return apology("Unable to insert into database.")

        # Updates the user's cash
        result2 = db.execute("UPDATE users SET cash = :_remain WHERE id = :currentid", _remain = remain, currentid = session["user_id"])

        return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    # Fetch rows from portfolio
    rows = db.execute("SELECT * FROM portfolio WHERE id = :currentid", currentid = session["user_id"])

    # Introduces a key called transaction and inputs, according to conditions, Buy and Sell strings
    for i in range(len(rows)):
        if rows[i]["shares"] < 0:
            rows[i]["transaction"] = "Sell"
            rows[i]["shares"] = - rows[i]["shares"]


        elif rows[i]["shares"] > 0:
             rows[i]["transaction"] = "Buy"

    return render_template("history.html", htmlrows = rows)


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


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # If user reached /quote via GET, return quote form
    if request.method == "GET":
        return render_template("quote.html")

    # If user submitted quote form, return quoted template including the requested stock
    elif request.method == "POST":
        stock = lookup(request.form.get("symbol"))

        # Checks if stock is valid
        if stock == None:
            return apology("Invalid stock submitted.", code=400)

        # If stock is valid, returns quoted template
        else:
            return render_template("quoted.html", symbol=stock["symbol"], price=usd(stock["price"]))


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # if method is GET, returns register template
    if request.method == "GET":
        return render_template("register.html")

    # if method is POST i.e. username submits register form, registers the user.
    elif request.method == "POST":
        # Check if username field left blank
        if not request.form.get("username"):
            return apology("Missing username!")

        # Check if password field left blank
        elif not request.form.get("password"):
            return apology("Missing password!")

        # Check if password confirmation field left blank
        elif not request.form.get("confirmation"):
            return apology("Missing password confirmation!")

        # Check if passwords don't match
        if not request.form.get("password") == request.form.get("confirmation"):
            return apology("Password and password confirmation don't match!")

        # Check if username already exists
        rows = db.execute("SELECT username FROM users")

        for i in range(len(rows)):
            if rows[i]["username"] == request.form.get("username"):
                return apology("Username already exists.")

        # Store username in a variable
        usern = request.form.get("username")

        # Hash and store password in a variable
        phash = generate_password_hash(request.form.get("password"))

        # result is a type and db.execute returns the value of the primary key if primary key was set to autoincrementing
        result = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hashz)", username = usern, hashz = phash)

        if not result:
            return apology("Could not insert into database.")

        # Login the registered user and redirect
        user_id = db.execute("SELECT id FROM users WHERE username = :usernam", usernam=request.form.get("username"))
        session["user_id"] = user_id[0]["id"]
        return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # get two rows, first for one sell operations, second for condition checking, containing stocks and their shares
    rows = db.execute("SELECT stock, SUM(shares) as sumshares FROM portfolio WHERE id = :currentid GROUP BY stock HAVING sumshares > 0", currentid = session["user_id"])

    # returns form if method is GET
    if request.method == "GET":

        # Checks if there are no stocks to sell
        if len(rows) == 0:
            return apology("No stocks to sell.")

        return render_template("sell.html", htmlrows = rows)

    # if form is submitted, sells it after checking for things
    elif request.method == "POST":

        # Checks if shares field was left blank
        if not request.form.get("shares"):
            return apology("Please enter number of shares you want to sell.")

        # Checks if submitted shares is positive and less than or equal to shares in portfolio
        for i in range(len(rows)):
            if rows[i]["stock"] == request.form.get("symbol"):
                if int(request.form.get("shares")) < 0:
                    return apology("Please enter a positive number.")

                elif int(request.form.get("shares")) > rows[i]["sumshares"]:
                    return apology("Not enough shares.")

        # Looks up a stock
        lookupstock = lookup(request.form.get("symbol"))

        # Declare values to be submitted into portfolio
        submittedstock = request.form.get("symbol")
        submittedshares = - int(request.form.get("shares"))
        positivesubmittedshares = int(request.form.get("shares"))
        currentstock = lookup(submittedstock)

        # Logs shares submitted as a negative quantity in portfolio, along with stock symbol
        result = db.execute("INSERT INTO portfolio (id, stock, shares, price) VALUES(:_id, :_stock, :_shares, :_price)", _id = session["user_id"], _stock = submittedstock, _shares = submittedshares, _price = currentstock["price"])
        if not result:
            return apology("Could not insert into database.")

        # Updates cash of the user
        cashlist = db.execute("SELECT cash FROM users WHERE id = :currentid", currentid = session["user_id"])
        cash = cashlist[0]["cash"]
        cash += positivesubmittedshares * currentstock["price"]
        result2 = db.execute("UPDATE users SET cash = :_cash WHERE id = :currentid", _cash = cash, currentid = session["user_id"])

        # Send "Transaction Complete!" message via html file
        return redirect("/")


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
