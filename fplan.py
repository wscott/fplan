#!/usr/bin/python3

import toml
import argparse
import scipy.optimize

# TODO
#   - RMD


# Minimize: c^T * x
# Subject to: A_ub * x <= b_ub

#vars: money, per year(savings, ira, roth, ira2roth)  (193 vars)
#all vars positive


# Instantiate the parser
parser = argparse.ArgumentParser()

parser.add_argument('conffile')
args = parser.parse_args()

with open(args.conffile) as conffile:
    S = toml.loads(conffile.read())
cg_tax = 0.15

numyr = S['endage'] - S['startage']
vper = 4        # variables per year (savings, ira, roth, ira2roth)

# optimize this poly (we want to maximize the money we can spend)
c = [-1] + [0] * vper * numyr

A = []
b = []

# 2017 table (could predict it moves with inflation?)
# only married joint at the moment
taxrates = [[0,     0.00, 0],
            [0.1,  0.10, 0.01],        # fake level to fix 0
            [18700,  0.15, 1900],
            [75900,  0.25, 10500],
            [153100, 0.28, 29800],
            [233400, 0.33, 52200],
            [415700, 0.35, 112400],
            [470000, 0.40, 131400]]
stded = 12700 + 2*4050                 # standard deduction
i_rate = 1 + S['inflation'] / 100       # inflation rate: 2.5 -> 1.025
r_rate = 1 + S['returns'] / 100         # invest rate: 6 -> 1.06

# spending each year needs to be more than goal after subtracting taxes
# we do the taxes for each tax bracket as a separate constraint. Only the
# current range will contrain the output.

# The constraint starts like this:
#   TAX = RATE * (IRA + IRA2ROTH + SS - SD - CUT) + BASE
#   CG_TAX = SAVINGS * (1-(BASIS/(S_BAL*rate^YR))) * 20%
#   GOAL + EXTRA >= SAVING + IRA + ROTH + SS - TAX
for year in range(numyr):
    i_mul = i_rate ** year
    for (cut, rate, base) in taxrates:
        row = [i_mul] + [0] * vper * numyr          # goal is positive
        cut *= i_mul
        base *= i_mul

        # aftertax basis
        basis = 1 - (S['aftertax']['basis'] /
                     (S['aftertax']['bal']*r_rate**year))

        # aftertax withdrawal + capital gains tax
        row[1+vper*year+0] = -1 + basis * cg_tax

        if year + S['startage'] < 59:
            row[1+vper*year+1] = -0.9 + rate    # 10% penelty
        else:
            row[1+vper*year+1] = -1 + rate      # IRA - tax

        # XXX How to model 10% penelty for Roth before 59 other than
        # contributions
        row[1+vper*year+2] = -1                 # Roth

        row[1+vper*year+3] = rate               # tax on Roth conversion
        A += [row]

        # extra money needed at start of plan
        if S['extra'] > 0:
            if year < S['extra_yr']:
                if year + 1 > S['extra_yr']:
                    base += S['extra']*(S['extra_yr'] - year)
                else:
                    base += S['extra']

        # social security (which is taxed)
        if S['startage'] + year >= 70:
            base -= S['socialsec']* i_mul * (1 - rate)

        # offset from having this taxrate from zero
        b += [(cut + stded) * rate * i_mul - base]

# final balance for savings needs to be positive
row = [0] + [0] * vper * numyr
for year in range(numyr):
    row[1+vper*year+0] = r_rate ** (numyr - year)
A += [row]
b += [S['aftertax']['bal'] * r_rate ** numyr]

# final balance for IRA needs to be positive
row = [0] + [0] * vper * numyr
for year in range(numyr):
    row[1+vper*year+1] = r_rate ** (numyr - year)
    row[1+vper*year+3] = r_rate ** (numyr - year)
A += [row]
b += [S['IRA']['bal'] * r_rate ** numyr]

# before 59, Roth can only spend from contributions
for year in range(min(numyr, 59-S['startage'])):
    row = [0] + [0] * vper * numyr
    for y in range(0, year-4):
        row[1+vper*y+3]=-1
    for y in range(year+1):
        row[1+vper*y+2]=1
    A += [row]
    if year < 5:
        b += [0]        # sum of convertions <= 0
    else:
        b += [S['roth']['bal']]

# after 59 all of Roth can be spent, but contributions need to age
# 5 years and the balance each year needs to be positive
for year in range(max(0,59-S['startage']),numyr+1):
    row = [0] + [0] * vper * numyr

    # remove previous withdrawls
    for y in range(year):
        row[1+vper*y+2] = r_rate ** (year - y)

    # add previous conversions, but we can only see things
    # converted more than 5 years ago
    for y in range(year-5):
        row[1+vper*y+3] = -r_rate ** (year - y)

    A += [row]
    # only see initial balance after it has aged
    if year <= 5:
        b += [0]
    else:
        b += [S['roth']['bal'] * r_rate ** year]

print("Num vars: ", len(c))
print("Num contraints: ", len(b))
res = scipy.optimize.linprog(c, A_ub=A, b_ub=b,
                             options={"disp": True,
                                      "bland": True,
                                      "tol": 1.0e-9})

print("Yearly spending <= ", 100*int(res.x[0]/100))
print()
print((" age" + " %6s" * 10) %
      ("saving", "spend", "IRA", "fIRA", "Roth", "fRoth", "IRA2R",
       "rate", "tax", "spend"))
savings = S['aftertax']['bal']
ira = S['IRA']['bal']
roth = S['roth']['bal']
ttax = 0.0
tspend = 0.0
for year in range(numyr):
    i_mul = i_rate ** year
    fsavings = res.x[1+year*vper]
    fira = res.x[1+year*vper+1]
    froth = res.x[1+year*vper+2]
    ira2roth = res.x[1+year*vper+3]
    income = fira + ira2roth - stded*i_mul
    if year + S['startage'] >= 70:
        income += S['socialsec']*i_mul
    if income < 0:
        income = 0
    for (cut, rate, base) in taxrates:
        cut *= i_mul
        base *= i_mul
        if income < cut:
            break
        c = cut
        r = rate
        b = base
    (cut, rate, base) = (c, r, b)
    tax = (income - cut) * rate + base

    # aftertax basis
    basis = 1 - (S['aftertax']['basis'] /
                 (S['aftertax']['bal']*r_rate**year))
    tax += fsavings * basis * cg_tax
    if S['startage'] + year < 59:
        tax += fira * 0.10
    ttax += tax
    spending = fsavings + fira + froth - tax
    tspend += spending
    if year + S['startage'] >= 70:
        spending += S['socialsec']*i_mul
    print((" %d:" + " %6.0f" * 10) %
          (year+S['startage'],
           savings/1000, fsavings/1000,
           ira/1000, fira/1000,
           roth/1000, froth/1000, ira2roth/1000,
           rate * 100, tax/1000, spending/1000))

    savings -= fsavings
    savings *= r_rate
    ira -= fira
    ira -= ira2roth
    ira *= r_rate
    roth -= froth
    roth += ira2roth
    roth *= r_rate


print("\ntotal spending: %.0f" % tspend)
print("total tax: %.0f (%.1f%%)" % (ttax, 100*ttax/tspend))
