# Retirement planner

This little calculator is a retirement planner designed to explore
optimial withdraws from savings and IRA accounts. It uses a Linear
Programming solution to maximize the minimum amount of money available
to spend. As a side effect it minimizes the taxes that needs to be
spent.

This is similar to the ideas of James Welch at www.i-orp.com but I
wanted to explore some new ideas. ORP continues to be a much more
complete tool. This version is mainly aimed at people who retire well
before age 59.5.

## Currently modeled

* aftertax, IRA and Roth spending
* IRA->Roth conversions
* Federal income tax on IRA spending with 2017 tables
* Simplistic capital gains, assuming an average cost basis, at a fixed 15%
* Roth withdraw limitations before age 59
* Early IRA withdrawals have a 10% penalty. (this is added to 'tax')
* inflation
* Required Minimum Distributions from IRA
* Arbitrary income or expenses happening at certain years. Income can be taxed or not.
  This is used to model Social Security

## Not modeled yet

* Early withdrawals from Roth gains are not modeled (only contributions)
* Recording when existing Roth contributions can be accessed in config file
* IRA 72(t) withdrawals

## Not modeled

* Any other taxes
* Income or a pre-retirement period
* new contributions to IRA or Roth

## Assumptions

* Taxes are only for Married filing jointly at the moment
* Only the standard deduction for 2 people
* age 59 is assumed to be past 59.5

## Installing

This program is written in Python and assumes the packages SciPy and
toml are installed.

run `pip install --user toml scipy numpy` to install these libraries
on most machines.

## Usage

* Copy `sample.toml` to a new file
* Edit with your information
* run `python3 ./fplan.py NEW.toml`

## Output

The output is a table by age with the following columns. All numbers
in table are in 1000s of dollars.

* save: amount in after-tax savings account
* send: send from savings this year
* IRA: balance of tax-deferred IRA acount
* fIRA: amount to pull from IRA this year. (before 59 with penalty)
* Roth: balance of tax-exempt Roth account
* fRoth: amount to pull from Roth this year
* IRA2R: money converted from the IRA to Roth this year
* rate: US tax bracket this year
* tax: tax spent this year (includes IRA 10% penlty)
* spend: net amount spent this year (includes income)
* extra: additional spending this year
