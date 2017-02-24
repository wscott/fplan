#!/usr/bin/python3

import toml
import argparse
import scipy.optimize
import re

def agelist(str):
    for x in str.split(','):
        m = re.match('^(\d+)(-(\d+)?)?$', x)
        if m:
            s = int(m.group(1))
            e = s
            if m.group(2):
                e = m.group(3)
                if e:
                    e = int(e)
                else:
                    e = 120
            for a in range(s,e+1):
                yield a
        else:
            raise Exception("Bad age " + str)

def parse_expenses(S):
    """ Return array of income/expense per year """
    INC = [0] * numyr
    EXP = [0] * numyr
    TAX = [0] * numyr

    for k,v in S.get('expense', {}).items():
        for age in agelist(v['age']):
            year = age - S['startage']
            if year < 0:
                continue
            elif year >= numyr:
                break
            else:
                amount = v['amount']
                if v.get('inflation'):
                    amount *= i_rate ** year
                EXP[year] += amount

    for k,v in S.get('income', {}).items():
        for age in agelist(v['age']):
            year = age - S['startage']
            if year < 0:
                continue
            elif year >= numyr:
                break
            else:
                amount = v['amount']
                if v.get('inflation'):
                    amount *= i_rate ** year
                INC[year] += amount
                if v.get('tax'):
                    TAX[year] += amount
    return (INC,EXP,TAX)

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

cg_tax = 0.15                   # capital gains tax rate

numyr = S.get('endage', 95) - S['startage']
vper = 4        # variables per year (savings, ira, roth, ira2roth)
n0 = 2          # num variables before per year starts
sepp_end = max(5, 59-S['startage'])     # first year you can spend IRA reserved for SEPP

# optimize this poly (we want to maximize the money we can spend)
c = [0] * (n0 + vper * numyr)
c[0] = -1

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

# Required Minimal Distributions from IRA starting with age 70
RMD = [27.4, 26.5, 25.6, 24.7, 23.8, 22.9, 22.0, 21.2, 20.3, 19.5,  # age 70-79
       18.7, 17.9, 17.1, 16.3, 15.5, 14.8, 14.1, 13.4, 12.7, 12.0,  # age 80-89
       11.4, 10.8, 10.2,  9.6,  9.1,  8.6,  8.1,  7.6,  7.1,  6.7,  # age 90-99
        6.3,  5.9,  5.5,  5.2,  4.9,  4.5,  4.2,  3.9,  3.7,  3.4,  # age 100+
        3.1,  2.9,  2.6,  2.4,  2.1,  1.9,  1.9,  1.9,  1.9,  1.9]

i_rate = 1 + S['inflation'] / 100       # inflation rate: 2.5 -> 1.025
r_rate = 1 + S['returns'] / 100         # invest rate: 6 -> 1.06

# spending each year needs to be more than goal after subtracting taxes
# we do the taxes for each tax bracket as a separate constraint. Only the
# current range will contrain the output.
(income,expenses,taxed) = parse_expenses(S)

# XXX new var must be zero
row = [0] * (n0 + vper * numyr)
row[1] = 1
A += [row]
b += [0]

# The constraint starts like this:
#   TAX = RATE * (IRA + IRA2ROTH + SS - SD - CUT) + BASE
#   CG_TAX = SAVINGS * (1-(BASIS/(S_BAL*rate^YR))) * 20%
#   GOAL + EXTRA >= SAVING + IRA + ROTH + SS - TAX
for year in range(numyr):
    i_mul = i_rate ** year

    # aftertax basis
    if S['aftertax']['basis'] > 0:
        basis = 1 - (S['aftertax']['basis'] /
                     (S['aftertax']['bal']*r_rate**year))
    else:
        basis = 1

    for (cut, rate, base) in taxrates:
        row = [0] * (n0 + vper * numyr)
        row[0] = i_mul                           # goal is positive
        cut *= i_mul
        base *= i_mul

        # aftertax withdrawal + capital gains tax
        row[n0+vper*year+0] = -1 + basis * cg_tax

        if year + S['startage'] < 59:
            row[n0+vper*year+1] = -0.9 + rate    # 10% penelty
        else:
            row[n0+vper*year+1] = -1 + rate      # IRA - tax

        # XXX How to model 10% penelty for Roth before 59 other than
        # contributions
        row[n0+vper*year+2] = -1                 # Roth

        row[n0+vper*year+3] = rate               # tax on Roth conversion
        A += [row]

        base -= income[year]                    # must spend all income this year (temp)
        base += expenses[year]
        base += taxed[year]*rate                # extra income is taxed

        # offset from having this taxrate from zero
        b += [(cut + stded) * rate * i_mul - base]

# final balance for savings needs to be positive
row = [0] * (n0 + vper * numyr)
inc = 0
for year in range(numyr):
    row[n0+vper*year+0] = r_rate ** (numyr - year)
    #if income[year] > 0:
    #    inc += income[year] * r_rate ** (numyr - year)
A += [row]
b += [S['aftertax']['bal'] * r_rate ** numyr + inc]

# any years with income need to be positive in aftertax
# for year in range(numyr):
#     if income[year] == 0:
#         continue
#     row = [0] * (n0 + vper * numyr)
#     inc = 0
#     for y in range(year):
#         row[n0+vpy*y+0] = r_rate ** (year - y)
#         inc += income[y] * r_rate ** (year - y)
#     A += [row]
#     b += [S['aftertax']['bal'] * r_rate ** year + inc]

# final balance for IRA needs to be positive
row = [0] * (n0 + vper * numyr)
for year in range(numyr):
    row[n0+vper*year+1] = r_rate ** (numyr - year)
    row[n0+vper*year+3] = r_rate ** (numyr - year)
A += [row]
b += [S['IRA']['bal'] * r_rate ** numyr]

# before 59, Roth can only spend from contributions
for year in range(min(numyr, 59-S['startage'])):
    row = [0] * (n0 + vper * numyr)
    for y in range(0, year-4):
        row[n0+vper*y+3]=-1
    for y in range(year+1):
        row[n0+vper*y+2]=1
    A += [row]
    if year < 5:
        b += [0]        # sum of convertions <= 0
    else:
        b += [S['roth']['bal']]

# after 59 all of Roth can be spent, but contributions need to age
# 5 years and the balance each year needs to be positive
for year in range(max(0,59-S['startage']),numyr+1):
    row = [0] * (n0 + vper * numyr)

    # remove previous withdrawls
    for y in range(year):
        row[n0+vper*y+2] = r_rate ** (year - y)

    # add previous conversions, but we can only see things
    # converted more than 5 years ago
    for y in range(year-5):
        row[n0+vper*y+3] = -r_rate ** (year - y)

    A += [row]
    # only see initial balance after it has aged
    if year <= 5:
        b += [0]
    else:
        b += [S['roth']['bal'] * r_rate ** year]

# starting with age 70 the user must take RMD payments
for year in range(max(0,70-S['startage']),numyr):
    row = [0] * (n0 + vper * numyr)
    age = year + S['startage']
    rmd = RMD[age - 70]

    # the gains from the initial balance minus any withdraws gives
    # the current balance.
    for y in range(year):
        row[n0+vper*y+1] = -(r_rate ** (year - y))
        row[n0+vper*y+3] = -(r_rate ** (year - y))

    # this year's withdraw times the RMD factor needs to be more than
    # the balance
    row[n0+vper*year+1] = -rmd

    A += [row]
    b += [-(S['IRA']['bal'] * r_rate ** year)]

print("Num vars: ", len(c))
print("Num contraints: ", len(b))
res = scipy.optimize.linprog(c, A_ub=A, b_ub=b,
                             options={"disp": True,
                                      #"bland": True,
                                      "tol": 1.0e-7,
                                      "maxiter": 3000})
if res.success == False:
    print(res)
    exit(1)

print("Yearly spending <= ", 100*int(res.x[0]/100))
print()
print((" age" + " %5s" * 11) %
      ("save", "spend", "IRA", "fIRA", "Roth", "fRoth", "IRA2R",
       "rate", "tax", "spend", "extra"))
savings = S['aftertax']['bal']
ira = S['IRA']['bal']
roth = S['roth']['bal']
ttax = 0.0
tspend = 0.0
for year in range(numyr):
    i_mul = i_rate ** year
    fsavings = res.x[n0+year*vper]
    fira = res.x[n0+year*vper+1]
    froth = res.x[n0+year*vper+2]
    ira2roth = res.x[n0+year*vper+3]
    inc = fira + ira2roth - stded*i_mul + taxed[year]

    #if income[year]:
    #    savings += income[year]

    if inc < 0:
        inc = 0
    for (cut, rate, base) in taxrates:
        cut *= i_mul
        base *= i_mul
        if inc < cut:
            break
        c = cut
        r = rate
        b = base
    (cut, rate, base) = (c, r, b)
    tax = (inc - cut) * rate + base

    # aftertax basis
    if S['aftertax']['basis'] > 0:
        basis = 1 - (S['aftertax']['basis'] /
                     (S['aftertax']['bal']*r_rate**year))
    else:
        basis = 1
    tax += fsavings * basis * cg_tax
    if S['startage'] + year < 59:
        tax += fira * 0.10
    ttax += tax
    extra = expenses[year] - income[year]
    spending = fsavings + fira + froth - tax - extra
    tspend += spending + extra
    print((" %d:" + " %5.0f" * 11) %
          (year+S['startage'],
           savings/1000, fsavings/1000,
           ira/1000, fira/1000,
           roth/1000, froth/1000, ira2roth/1000,
           rate * 100, tax/1000, spending/1000, extra/1000))

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
