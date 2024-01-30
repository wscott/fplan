#!/usr/bin/env python3

import argparse
import re
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
import scipy.optimize


# Required Minimal Distributions from IRA starting with age 70
RMD = [27.4, 26.5, 25.6, 24.7, 23.8, 22.9, 22.0, 21.2, 20.3, 19.5,  # age 70-79
       18.7, 17.9, 17.1, 16.3, 15.5, 14.8, 14.1, 13.4, 12.7, 12.0,  # age 80-89
       11.4, 10.8, 10.2,  9.6,  9.1,  8.6,  8.1,  7.6,  7.1,  6.7,  # age 90-99
        6.3,  5.9,  5.5,  5.2,  4.9,  4.5,  4.2,  3.9,  3.7,  3.4,  # age 100+
        3.1,  2.9,  2.6,  2.4,  2.1,  1.9,  1.9,  1.9,  1.9,  1.9]

cg_tax = 0.15                   # capital gains tax rate

def agelist(str):
    for x in str.split(','):
        m = re.match(r'^(\d+)(-(\d+)?)?$', x)
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

class Data:
    def load_file(self, file):
        global vper
        with open(file) as conffile:
            d = tomllib.loads(conffile.read())
        self.i_rate = 1 + d.get('inflation', 0) / 100       # inflation rate: 2.5 -> 1.025
        self.r_rate = 1 + d.get('returns', 6) / 100         # invest rate: 6 -> 1.06

        self.startage = d['startage']
        self.endage = d.get('endage', max(96, self.startage+5))

        # 2023 tax table (could predict it moves with inflation?)
        # married joint at the moment, can override in config file
        default_taxrates = [[0,      10], 
                            [22000,  12],
                            [89450 , 22],
                            [190750, 24],
                            [364200, 32],
                            [462500, 35],
                            [693750, 37]]
        default_stded = 27700
        tmp_taxrates = default_taxrates
        if 'taxes' in d:
            tmp_taxrates = d['taxes'].get('taxrates', default_taxrates)
            self.stded = d['taxes'].get('stded', default_stded)
            self.state_tax = d['taxes'].get('state_rate', 0)
            self.state_cg_tax = d['taxes'].get('state_cg_rate', self.state_tax)
        else:
            self.stded = default_stded
            self.state_tax = 0
            self.state_cg_tax = 0
        # add fake level and switch to decimals
        tmp_taxrates[:0] = [[0, 0]]
        self.taxrates = [[x,y/100.0] for (x,y) in tmp_taxrates]
        cutoffs = [x[0] for x in self.taxrates][1:] + [float('inf')]
        self.taxtable = list(map(lambda x, y: [x[1], x[0], y], self.taxrates, cutoffs))

        self.state_tax = self.state_tax / 100.0
        self.state_cg_tax = self.state_cg_tax / 100.0

        # add columns for the standard deduction, tax brackets, 
        # state bracket (one for now),
        # and total taxes (for debugging)
        vper += 1 + len(self.taxtable) + 1 + 1

        if 'prep' in d:
            self.workyr = d['prep']['workyears']
            self.maxsave = d['prep']['maxsave']
            self.maxsave_inflation = d['prep'].get('inflation', True)
            self.worktax = 1 + d['prep'].get('tax_rate', 25)/100
        else:
            self.workyr = 0
        self.retireage = self.startage + self.workyr
        self.numyr = self.endage - self.retireage

        self.aftertax = d.get('aftertax', {'bal': 0})
        if 'basis' not in self.aftertax:
            self.aftertax['basis'] = 0

        self.IRA = d.get('IRA', {'bal': 0})
        if 'maxcontrib' not in self.IRA:
            self.IRA['maxcontrib'] = 19500 + 7000*2

        self.roth = d.get('roth', {'bal': 0})
        if 'maxcontrib' not in self.roth:
            self.roth['maxcontrib'] = 7000*2
        if 'contributions' not in self.roth:
            self.roth['contributions'] = []

        self.parse_expenses(d)
        self.sepp_end = max(5, 59-self.retireage)  # first year you can spend IRA reserved for SEPP
        self.sepp_ratio = 25                       # money per-year from SEPP  (bal/ratio)

    def parse_expenses(self, S):
        """ Return array of income/expense per year """
        INC = [0] * self.numyr
        EXP = [0] * self.numyr
        TAX = [0] * self.numyr

        for k,v in S.get('expense', {}).items():
            for age in agelist(v['age']):
                year = age - self.retireage
                if year < 0:
                    continue
                elif year >= self.numyr:
                    break
                else:
                    amount = v['amount']
                    if v.get('inflation'):
                        amount *= self.i_rate ** (year + self.workyr)
                    EXP[year] += amount

        for k,v in S.get('income', {}).items():
            for age in agelist(v['age']):
                year = age - self.retireage
                if year < 0:
                    continue
                elif year >= self.numyr:
                    break
                else:
                    amount = v['amount']
                    if v.get('inflation'):
                        amount *= self.i_rate ** (year + self.workyr)
                    INC[year] += amount
                    if v.get('tax'):
                        TAX[year] += amount
        self.income = INC
        self.expenses = EXP
        self.taxed = TAX

# Minimize: c^T * x
# Subject to: A_ub * x <= b_ub
#vars: money, per year(savings, ira, roth, ira2roth)  (193 vars)
#all vars positive
def solve(args):
    # optimize this poly (we want to maximize the money we can spend)
    nvars = n1 + vper * (S.numyr + S.workyr)
    c = [0] * nvars
    c[0] = -1

    # put the <= constrtaints here
    A = []
    b = []

    # put the equality constraints here
    AE = []
    be = []

    if not args.sepp:
        # force SEPP to zero
        row = [0] * nvars
        row[1] = 1
        A += [row]
        b += [0]

    # Work contributions don't exceed limits
    for year in range(S.workyr):
        # can't exceed maxsave per year
        row = [0] * nvars
        row[n1+year*vper+0] = S.worktax
        row[n1+year*vper+1] = 1
        row[n1+year*vper+2] = S.worktax
        A += [row]
        if S.maxsave_inflation:
            b += [S.maxsave * S.i_rate ** year]
        else:
            b += [S.maxsave]

        # max IRA per year
        row = [0] * nvars
        row[n1+year*vper+1] = 1
        A += [row]
        b += [S.IRA['maxcontrib'] * S.i_rate ** year]

        # max Roth per year
        row = [0] * nvars
        row[n1+year*vper+2] = 1
        A += [row]
        b += [S.roth['maxcontrib'] * S.i_rate ** year]

    # The constraint starts like this:
    #   TAX = RATE * (IRA + IRA2ROTH + SS - SD - CUT) + BASE
    #   CG_TAX = SAVINGS * (1-(BASIS/(S_BAL*rate^YR))) * 20%
    #   GOAL + EXTRA >= SAVING + IRA + ROTH + SS - TAX
    for year in range(S.numyr):
        i_mul = S.i_rate ** (year + S.workyr)
        n_fsave = n0+vper*year+0
        n_fira = n0+vper*year+1
        n_froth = n0+vper*year+2
        n_ira2roth = n0+vper*year+3
        n_stded = n0+vper*year+4
        n_taxtable = n0+vper*year+5
        n_state = n0+vper*year+5 + len(S.taxtable)
        n_taxes = n0+vper*year+vper-1

        # aftertax basis
        # XXX fix work contributions
        if S.aftertax['basis'] > 0:
            basis = 1 - (S.aftertax['basis'] /
                         (S.aftertax['bal']*S.r_rate**(year + S.workyr)))
        else:
            basis = 1


        # limit how much can be considered part of the standard deduction
        row = [0] * nvars
        row[n_stded] = 1
        A += [row]
        b += [S.stded * i_mul]

        for idx, (rate, low, high) in enumerate(S.taxtable[0:-1]):
            # limit how much can be put in each tax bracket
            row = [0] * nvars
            row[n_taxtable+idx] = 1
            A += [row]
            b += [(high - low) * i_mul]

        # the sum of everything in the std deduction + tax brackets must 
        # be equal to fira + ira2roth + taxed_extra
        row = [0] * nvars
        row[n_fira] = 1
        row[n_ira2roth] = 1
        row[n_stded] = -1
        for idx in range(len(S.taxtable)):
            row[n_taxtable+idx] = -1
        AE += [row]
        be += [-S.taxed[year]]
       
        # the sum of everything in the std deduction + state tax brackets must 
        # be equal to fira + ira2roth + taxed_extra
        row = [0] * nvars
        row[n_fira] = 1
        row[n_ira2roth] = 1
        row[n_stded] = -1
        row[n_state] = -1
        AE += [row]
        be += [-S.taxed[year]]

        # calc total taxes
        row = [0] * nvars
        row[n_taxes] = 1                    # this is where we will store total taxes
        if year + S.retireage < 59:         # ira penalty
            row[n_fira] = -0.1
        row[n_fsave] = -basis * (cg_tax + S.state_cg_tax)
        row[n_froth] = -0
        row[n_stded] = -0
        for idx, (rate, low, high) in enumerate(S.taxtable):
            row[n_taxtable+idx] = -rate
        row[n_state] = -S.state_tax
        AE += [row]
        be += [0]

        # calc that everything withdrawn must equal spending money + total taxes
        row = [0] * nvars
        # spendable money
        row[n_fsave] = 1
        row[n_fira] = 1
        row[n_froth] = 1
        # spent money
        row[0] -= i_mul                     # spending floor
        row[n_taxes] = -1                   # taxes as computed earlier
        AE += [row]
        be += [-S.income[year] + S.expenses[year]]
       

    # final balance for savings needs to be positive
    row = [0] * nvars
    inc = 0
    for year in range(S.numyr):
        row[n0+vper*year+0] = S.r_rate ** (S.numyr - year)
        #if S.income[year] > 0:
        #    inc += S.income[year] * S.r_rate ** (S.numyr - year)
    for year in range(S.workyr):
        row[n1+vper*year+0] = -(S.r_rate ** (S.numyr + S.workyr - year))
    A += [row]
    b += [S.aftertax['bal'] * S.r_rate ** (S.workyr + S.numyr) + inc]

    # any years with income need to be positive in aftertax
    # for year in range(S.numyr):
    #     if S.income[year] == 0:
    #         continue
    #     row = [0] * nvars
    #     inc = 0
    #     for y in range(year):
    #         row[n0+vpy*y+0] = S.r_rate ** (year - y)
    #         inc += S.income[y] * S.r_rate ** (year - y)
    #     A += [row]
    #     b += [S.aftertax['bal'] * S.r_rate ** year + inc]

    # final balance for IRA needs to be positive
    row = [0] * nvars
    for year in range(S.numyr):
        row[n0+vper*year+1] = S.r_rate ** (S.numyr - year)
        row[n0+vper*year+3] = S.r_rate ** (S.numyr - year)
        if year < S.sepp_end:
            row[1] += (1/S.sepp_ratio) * S.r_rate ** (S.numyr - year)
    for year in range(S.workyr):
        row[n1+vper*year+1] = -(S.r_rate ** (S.numyr + S.workyr - year))
    A += [row]
    b += [S.IRA['bal'] * S.r_rate ** (S.workyr + S.numyr)]

    # IRA balance at SEPP end needs to not touch SEPP money
    row = [0] * nvars
    for year in range(S.sepp_end):
        row[n0+vper*year+1] = S.r_rate ** (S.sepp_end - year)
        row[n0+vper*year+3] = S.r_rate ** (S.sepp_end - year)
    for year in range(S.workyr):
        row[n1+vper*year+1] = -(S.r_rate ** (S.sepp_end + S.workyr - year))
    row[1] = S.r_rate ** S.sepp_end
    A += [row]
    b += [S.IRA['bal'] * S.r_rate ** S.sepp_end]

    # before 59, Roth can only spend from contributions
    for year in range(min(S.numyr, 59-S.retireage)):
        row = [0] * nvars
        for y in range(0, year-4):
            row[n0+vper*y+3] = -1
        for y in range(year+1):
            row[n0+vper*y+2] = 1

        # include contributions while working
        for y in range(min(S.workyr, S.workyr-4+year)):
            row[n1+vper*y+2] = -1

        A += [row]
        # only see initial balance after it has aged
        contrib = 0
        for (age, amount) in S.roth['contributions']:
            if age + 5 - S.retireage <= year:
                contrib += amount
        b += [contrib]

    # after 59 all of Roth can be spent, but contributions need to age
    # 5 years and the balance each year needs to be positive
    for year in range(max(0,59-S.retireage),S.numyr+1):
        row = [0] * nvars

        # remove previous withdrawls
        for y in range(year):
            row[n0+vper*y+2] = S.r_rate ** (year - y)

        # add previous conversions, but we can only see things
        # converted more than 5 years ago
        for y in range(year-5):
            row[n0+vper*y+3] = -S.r_rate ** (year - y)

        # add contributions from work period
        for y in range(S.workyr):
            row[n1+vper*y+2] = -S.r_rate ** (S.workyr + year - y)

        A += [row]
        # initial balance
        b += [S.roth['bal'] * S.r_rate ** (S.workyr + year)]

    # starting with age 70 the user must take RMD payments
    for year in range(max(0,70-S.retireage),S.numyr):
        row = [0] * nvars
        age = year + S.retireage
        rmd = RMD[age - 70]

        # the gains from the initial balance minus any withdraws gives
        # the current balance.
        for y in range(year):
            row[n0+vper*y+1] = -(S.r_rate ** (year - y))
            row[n0+vper*y+3] = -(S.r_rate ** (year - y))
            if year < S.sepp_end:
                row[1] -= (1/S.sepp_ratio) * S.r_rate ** (year - y)

        # include deposits during work years
        for y in range(S.workyr):
            row[n1+vper*y+1] = S.r_rate ** (S.workyr + year - y)

        # this year's withdraw times the RMD factor needs to be more than
        # the balance
        row[n0+vper*year+1] = -rmd

        A += [row]
        b += [-(S.IRA['bal'] * S.r_rate ** (S.workyr + year))]

    if args.verbose:
        print("Num vars: ", len(c))
        print("Num contraints: ", len(b))
    res = scipy.optimize.linprog(c, A_ub=A, b_ub=b, A_eq=AE, b_eq=be, method="highs-ipm",
                                 options={"disp": args.verbose})
    if res.success == False:
        print(res)
        exit(1)

    return res.x

def print_ascii(res):
    print("Yearly spending <= ", 100*int(res[0]/100))
    sepp = 100*int(res[1]/100)
    print("SEPP amount = ", sepp, sepp / S.sepp_ratio)
    print()
    savings = S.aftertax['bal']
    ira = S.IRA['bal']
    roth = S.roth['bal']
    if S.workyr > 0:
        print((" age" + " %5s" * 6) %
              ("save", "tSAVE", "IRA", "tIRA", "Roth", "tRoth"))
    for year in range(S.workyr):
        fsavings = res[n1+year*vper]
        fira = res[n1+year*vper+1]
        froth = res[n1+year*vper+2]
        print((" %d:" + " %5.0f" * 6) %
              (year+S.startage,
               savings/1000, fsavings/1000,
               ira/1000, fira/1000,
               roth/1000, froth/1000))
        savings += fsavings
        savings *= S.r_rate
        ira += fira
        ira *= S.r_rate
        roth += froth
        roth *= S.r_rate

    print((" age" + " %5s" * 12) %
          ("save", "fsave", "IRA", "fIRA", "SEPP", "Roth", "fRoth", "IRA2R",
           "rate", "tax", "spend", "extra"))
    ttax = 0.0
    tspend = 0.0
    for year in range(S.numyr):
        i_mul = S.i_rate ** (year + S.workyr)
        fsavings = res[n0+year*vper]
        fira = res[n0+year*vper+1]
        froth = res[n0+year*vper+2]
        ira2roth = res[n0+year*vper+3]
        if year < S.sepp_end:
            sepp_spend = sepp/S.sepp_ratio
        else:
            sepp_spend = 0
        inc = fira + ira2roth - S.stded*i_mul + S.taxed[year] + sepp_spend

        tax = res[n0+year*vper+vper-1]
        rate = next(r for (r, l, h) in S.taxtable if (inc <= h*i_mul)) + S.state_tax

        #if S.income[year]:
        #    savings += S.income[year]

        extra = S.expenses[year] - S.income[year]
        spending = fsavings + fira + froth - tax - extra + sepp_spend

        ttax += tax / i_mul                     # totals in today's dollars
        tspend += (spending + extra) / i_mul    # totals in today's dollars
        print((" %d:" + " %5.0f" * 12) %
              (year+S.retireage,
               savings/1000, fsavings/1000,
               ira/1000, fira/1000, sepp_spend/1000,
               roth/1000, froth/1000, ira2roth/1000,
               rate * 100, tax/1000, spending/1000, extra/1000))

        savings -= fsavings
        savings *= S.r_rate
        ira -= fira + sepp_spend + ira2roth
        ira *= S.r_rate
        roth -= froth
        roth += ira2roth
        roth *= S.r_rate

    print("\ntotal spending: %.0f" % tspend)
    print("total tax: %.0f (%.1f%%)" % (ttax, 100*ttax/(tspend+ttax)))


def print_csv(res):
    print("spend goal,%d" % res[0])
    print("savings,%d,%d" % (S.aftertax['bal'], S.aftertax['basis']))
    print("ira,%d" % S.IRA['bal'])
    print("roth,%d" % S.roth['bal'])

    print("age,fsave,fIRA,fROTH,IRA2R,income,expense")
    for year in range(S.numyr):
        fsavings = res[n0+year*vper]
        fira = res[n0+year*vper+1]
        froth = res[n0+year*vper+2]
        ira2roth = res[n0+year*vper+3]
        print(("%d," * 6 + "%d") % (year+S.retireage,fsavings,fira,froth,ira2roth,
                                    S.income[year],S.expenses[year]))

def main():
    # Instantiate the parser
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true',
                        help="Extra output from solver")
    parser.add_argument('--sepp', action='store_true',
                        help="Enable SEPP processing")
    parser.add_argument('--csv', action='store_true', help="Generate CSV outputs")
    parser.add_argument('--validate', action='store_true',
                        help="compare single run to separate runs")
    parser.add_argument('conffile')
    args = parser.parse_args()

    global S
    global vper, n1
    vper = 4        # variables per year (savings, ira, roth, ira2roth)
    n1 = 2          # before-retire years start here
    S = Data()
    S.load_file(args.conffile)

    global n0
    n0 = n1+S.workyr*vper   # post-retirement years start here

    res = solve(args)
    if args.csv:
        print_csv(res)
    else:
        print_ascii(res)

    if args.validate:
        for y in range(1,nyears):
            pass

if __name__== "__main__":
    main()
