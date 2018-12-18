from __future__ import print_function
import sys

# You will probably need more methods from flask but this one is a good start.
from flask import render_template, request

# Import things from Flask that we need.
from accounting import app, db, utils

# Import our models
from models import Contact, Invoice, Policy

# Import error for no results found on sql query.
from sqlalchemy.orm.exc import NoResultFound

from datetime import date


# Routing for the main web application.
@app.route("/", methods=['GET', 'POST'])
def index():
    #  Uses POST to search for policies by policy number and date.
    if request.method == 'POST':
        # Splitting policy number by space, capitalizing both words, and
        # joining them on a space.
        policy_number_input = \
            ' '.join(word.capitalize()
                     for word in request.form['policy-number']
                                        .lower().split(" "))
        print(policy_number_input, file=sys.stderr)

        policy_date = request.form['policy-date']

        print(policy_date, file=sys.stderr)
        try:
            policy_acc = utils.PolicyAccounting(Policy.query.filter_by(
                                             policy_number=policy_number_input,
                                             effective_date=policy_date).one()
                                                                        .id)

        # If no policy is found, return index.html with error message.
        except NoResultFound:
            return render_template('index.html', no_results=True)

        policy_balance = policy_acc.return_account_balance()
        invoices = Invoice.query.filter_by(policy_id=policy_acc.policy.id) \
                                .all()

        # Building invoice table data for html table.
        final_invoices = []
        for invoice in invoices:
            final_invoices.append([invoice.id,
                                  invoice.bill_date,
                                  invoice.due_date,
                                  invoice.cancel_date,
                                  invoice.amount_due])

        return render_template('index.html', policybalance=policy_balance,
                               data=final_invoices)
    else:
        return render_template('index.html')