# Retirement planner

This little calculator is a retirement planner designed to explore
optimial withdraws from savings and IRA accounts. It uses a Linear
Programming solution to maximize the minimum abount of money available
to spend. As a side effect it minimizes the taxes that needs to be
spend.

This is similar to the ideas at www.i-orp.com but I wanted to explore
some new ideas.

## Currently modeled

* aftertax, IRA and Roth spending
* IRA->Roth conversions
* Federal income tax on IRA spending with 2017 tables
* Simplistic capital gains assuming an average cost basis at a fixed 15%
* Roth withdraw limitations before age 59

## Not modeled yet

* inflation
* Required Minimum Distributions from IRA
* Existing Roth contribution dates for before 59 withdraws

## Not modeled

* Any other taxes
* Incoming
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
