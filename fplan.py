#!/usr/bin/python3

# TODO
#   - Model inflation
#     - scales: spending, tax brackets, SS

# Minimize: c^T * x
# Subject to: A_ub * x <= b_ub

#vars: money, per year(savings, ira, roth, ira2roth)  (193 vars)
#all vars positive

returns = 1.06  # 6%
startage = 47
endage = 100    # 99 is last year simulated
bal = [406, 880, 117]           # starting balance
# roth money is assumed to be all deposited at start of plan
# XXX need ability to separate contributions from earnings and
#     when the contributions are spendable
socialsec = 5
extra = 1.5                     # extra spending per month at beginning
extra_months = 8.5 * 12         # models current mortgage

# mmm
#startage = 35
#bal = [100, 650, 0]
#extra = 0
#returns = 1.09

numyr = endage - startage
vper = 4        # variables per year (savings, ira, roth, ira2roth)

# optimize this poly (we want to maximize the money we can spend)
c = [-1] + [0] * vper * numyr

A = []
b = []

# 2017 table (could predict it moves with inflation?)
taxrates = [[0,     0.10, 0],
            [18.7,  0.15, 1.9],
            [75.9,  0.25, 10.5],
            [153.1, 0.28, 29.8],
            [233.4, 0.33, 52.2],
            [415.7, 0.35, 112.4],
            [470.0, 0.40, 131.4]]
stded = 12.7                    # standard deduction

# spending each year needs to be more than goal after subtracting taxes
# we do the taxes for each tax bracket as a separate constraint. Only the
# current range will contrain the output.

# The constraint starts like this:
#   TAX = RATE * (IRA + IRA2ROTH + SS - SD - CUT) + BASE
#   GOAL + EXTRA >= SAVING + IRA + ROTH + SS - TAX
for year in range(numyr):
    for (cut, rate, base) in taxrates:
        row = [1] + [0] * vper * numyr
        row[1+vper*year+0] = -1            # savings
        if year + startage < 59:
            row[1+vper*year+1] = -0.9 + rate     # 10% penelty
        else:
            row[1+vper*year+1] = -1 + rate       # IRA - tax
        row[1+vper*year+2] = -1            # Roth
        row[1+vper*year+3] = rate          # tax on Roth conversion
        A += [row]
        if extra_months - year*12 > 12:
            base += extra*12
        elif extra_months - year*12 > 0:
            base += extra*(extra_months - year*12)
        if startage + year >= 70:
            base -= socialsec - socialsec * rate

        # offset from having this taxrate from zero
        b += [(cut + stded) * rate - base]

# final balance for savings
row = [0] + [0] * vper * numyr
for year in range(numyr):
    row[1+vper*year+0] = returns ** (numyr - year)
A += [row]
b += [bal[0] * returns ** numyr]

# final balance for IRA
row = [0] + [0] * vper * numyr
for year in range(numyr):
    row[1+vper*year+1] = returns ** (numyr - year)
    row[1+vper*year+3] = returns ** (numyr - year)
A += [row]
b += [bal[1] * returns ** numyr]

# at each year balance of Roth should be positive
for year in range(1,numyr):
    row = [0] + [0] * vper * numyr

    # remove previous withdrawls
    for y in range(year):
        row[1+vper*y+2] = returns ** (year - y)

    # add previous conversions, but we can only see things
    # converted more than 5 years ago
    for y in range(year-5):
        row[1+vper*y+3] = -returns ** (year - y)

    A += [row]
    # only see initial balance after it has aged
    if year <= 5:
        b += [0]
    else:
        b += [bal[2] * returns ** year]

# before 59 roth withdraws only from conversions
if startage < 59:
    for year in range(59 - startage):
        row = [0] + [0] * vper * numyr
        for y in range(0, year-5):
            row[1+vper*y+3]=-1
        for y in range(year):
            row[1+vper*y+2]=1
        A += [row]
        if year <= 5:
            b += [0]        # sum of convertions <= 0
        else:
            b += [bal[2]]

print("Num vars: ", len(c))
print("Num contraints: ", len(b))
import scipy.optimize
res = scipy.optimize.linprog(c, A_ub=A, b_ub=b, options={"disp": True})

print((" age" + " %6s" * 10) %
      ("saving", "spend", "IRA", "fIRA", "Roth", "fRoth", "IRA2R",
       "rate", "tax", "spend"))
savings = bal[0]
ira = bal[1]
roth = bal[2]
for year in range(numyr):
    fsavings = res.x[1+year*vper]
    fira = res.x[1+year*vper+1]
    froth = res.x[1+year*vper+2]
    ira2roth = res.x[1+year*vper+3]
    income = fira + ira2roth - stded
    if year + startage >= 70:
        income += socialsec
    if income < 0:
        income = 0
    for (cut, rate, base) in taxrates:
        if income <= cut:
            break
        c = cut
        r = rate
        b = base
    (cut, rate, base) = (c, r, b)
    tax = (income - cut) * rate + base
    if startage + year < 59:
        tax += fira * 0.10
    spending = fsavings + fira + froth - tax
    if year + startage >= 70:
        spending += socialsec
    print((" %d:" + " %6.0f" * 10) %
          (year+startage,
           savings, fsavings,
           ira, fira,
           roth, froth, ira2roth,
           rate * 100, tax, spending))
    savings -= fsavings
    savings *= returns
    ira -= fira
    ira -= ira2roth
    ira *= returns
    roth -= froth
    roth += ira2roth
    roth *= returns
