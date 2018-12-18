#!/user/bin/env python2.7

from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

from accounting import db
from models import Contact, Invoice, Payment, Policy
from sqlalchemy.orm.exc import NoResultFound

"""
#######################################################
This is the base code for the engineer project.
#######################################################
"""


class PolicyAccounting(object):
    """
     Each policy has its own instance of accounting.
    """
    def __init__(self, policy_id):
        self.policy = Policy.query.filter_by(id=policy_id).one()

        if not self.policy.invoices:
            self.make_invoices()

    def return_account_balance(self, date_cursor=None):
        """
        Collects invoices and payments using self.policy.id, queries database
        for invoices and payments with that policy_id from the current date or
        before. Iterates over invoices and adds invoice.amount_due to due_now.
        Iterates over payments and subtracts payment.amount_paid from due_now.
        Returns due_now.
        """
        if not date_cursor:
            date_cursor = datetime.now().date()

        invoices = Invoice.query.filter_by(policy_id=self.policy.id)\
                                .filter(Invoice.bill_date <= date_cursor)\
                                .order_by(Invoice.bill_date)\
                                .all()
        due_now = 0
        for invoice in invoices:
            due_now += invoice.amount_due

        payments = Payment.query.filter_by(policy_id=self.policy.id)\
                                .filter(Payment.transaction_date <=
                                        date_cursor)\
                                .all()
        for payment in payments:
            due_now -= payment.amount_paid

        return due_now

    def make_payment(self, contact_id=None, date_cursor=None, amount=0):
        """
        Adds a payment to payments table. Checks for contact_id. If there is no
        contact_id, check for self.policy.named_insured. If there is none,
        trigger an exception. Ensures only agents may make payments on
        cancellation_pending_due_to_non_pay invoices.
        """

        if not date_cursor:
            date_cursor = datetime.now().date()

        if not contact_id:
            try:
                contact_id = self.policy.named_insured
            except Exception:
                pass

        if self.evaluate_cancellation_pending_due_to_non_pay(
                date_cursor) is True and \
                Contact.query.filter_by(id=contact_id).one().role != "Agent":
            print("Only an agent may make a payment on this invoice.")
            return

        payment = Payment(self.policy.id,
                          contact_id,
                          amount,
                          date_cursor)
        db.session.add(payment)
        db.session.commit()

        return payment

    def evaluate_cancellation_pending_due_to_non_pay(self, date_cursor=None):
        """
         If this function returns true, an invoice
         on a policy has passed the due date without
         being paid in full. However, it has not necessarily
         made it to the cancel_date yet.
        """
        if not date_cursor:
            date_cursor = datetime.now().date()

        if self.return_account_balance(date_cursor -
                                       timedelta(days=1)) > 0:
            return True

    def evaluate_cancel(self, date_cursor=None, cancellation_reason=None,
                        cancellation_description=None):
        """
        If there is no cancellation reason: checks if invoice contains an
        account balance. Queries using policy id and date to look for invoices
        with cancel dates less than the date_cursor. If any invoice returns an
        account balance, set cancellation_reason, description, and date. If
        there is no cancellation_reason and no account_balances remaining,
        print that the policy should not cancel and return. Otherwise, set the
        policy.cancellation items equal to cancellation_reason,
        cancellation_description, and cancellation_date followed by printing
        the cancellation information to the screen.
        """
        if not date_cursor:
            date_cursor = datetime.now().date()

        invoices = Invoice.query.filter_by(policy_id=self.policy.id)\
                                .filter(Invoice.cancel_date <= date_cursor)\
                                .order_by(Invoice.bill_date)\
                                .all()
        if not cancellation_reason:
            for invoice in invoices:
                if not self.return_account_balance(invoice.cancel_date):
                    continue
                else:
                    cancellation_reason = "Past Due Payments"
                    cancellation_description = "Invoice ID: " + invoice.id + \
                        "Due Date: " + invoice.due_date + "Amount Due:" + \
                        invoice.amount_due
                    break

            print "THIS POLICY SHOULD NOT CANCEL"

            return

        self.policy.status = "Canceled"
        self.policy.cancellation_reason = cancellation_reason
        self.policy.cancellation_description = cancellation_description
        self.policy.cancellation_date = date_cursor

        db.session.commit()

        print "Policy canceled on " + str(date_cursor) + " for " + \
              cancellation_reason + ": " + cancellation_description


    def change_billing_schedule(self,  billing_schedule, date_cursor=None):
        """
        Changes billing schedule for all invoices past the date provided then
        uses make_invoices to mark old invoices as deleted and create using
        make_invoices.
        """
        if not date_cursor:
            date_cursor = datetime.now().date()

        self.policy.billing_schedule = billing_schedule

        self.make_invoices(date_cursor)

    def make_invoices(self, date_cursor=None):
        """
        Removes invoices for current policy and replaces them with newly
        created invoices. If date is passed, delete and recreate only invoices
        on or after that date. Queries for first invoice to determine
        billing_schedule and amount_due. amount due is divided by the number
        of invoices and the number of invoices is generated based on what is
        required by the billing_schedule. Date object needs to be passed, not a
        string
        """
        if not date_cursor:
            date_cursor = self.policy.effective_date
            total_remaining = self.policy.annual_premium
        else:
            total_remaining = 0

        invoices = Invoice.query.filter_by(policy_id=self.policy.id)\
                                .filter(Invoice.bill_date >= date_cursor)\
                                .order_by(Invoice.bill_date)\
                                .all()

        if total_remaining == 0:
            for invoice in invoices:
                total_remaining += invoice.amount_due
                invoice.deleted = True
                db.session.add(invoice)
        else:
            for invoice in invoices:
                invoice.deleted = True
                db.session.add(invoice)

        db.session.commit()

        billing_schedules = {'Annual': None, 'Semi-Annual': 3, 'Quarterly': 4,
                             'Two-Pay': 2, 'Monthly': 12}

        invoices = []
        first_invoice = Invoice(self.policy.id,
                                date_cursor,  # bill_date
                                date_cursor + \
                                relativedelta(months=1),  # due
                                date_cursor + \
                                relativedelta(months=1, days=14),  # cancel
                                total_remaining)
        invoices.append(first_invoice)

        if self.policy.billing_schedule == "Annual":
            pass
        elif self.policy.billing_schedule == "Two-Pay":
            first_invoice.amount_due = first_invoice.amount_due / \
                            billing_schedules.get(self.policy.billing_schedule)
            for i in range(1, billing_schedules.get(self.policy
                                                    .billing_schedule)):
                months_after_eff_date = i*6
                bill_date = date_cursor + \
                    relativedelta(months=months_after_eff_date)
                invoice = Invoice(self.policy.id,
                                  bill_date,
                                  bill_date + relativedelta(months=1),
                                  bill_date + relativedelta(months=1, days=14),
                                  total_remaining /
                                  billing_schedules.get(self.policy
                                                        .billing_schedule))
                invoices.append(invoice)
        elif self.policy.billing_schedule == "Quarterly":
            first_invoice.amount_due = first_invoice.amount_due / \
                        billing_schedules.get(self.policy.billing_schedule)
            for i in range(1, billing_schedules.get(self.policy
                                                    .billing_schedule)):
                months_after_eff_date = i*3
                bill_date = date_cursor + \
                    relativedelta(months=months_after_eff_date)
                invoice = Invoice(self.policy.id,
                                  bill_date,
                                  bill_date + relativedelta(months=1),
                                  bill_date + relativedelta(months=1, days=14),
                                  total_remaining /
                                  billing_schedules.get(self.policy
                                                        .billing_schedule))
                invoices.append(invoice)
        elif self.policy.billing_schedule == "Monthly":
            first_invoice.amount_due = first_invoice.amount_due / \
                            billing_schedules.get(self.policy.billing_schedule)
            for i in range(1, billing_schedules.get(self.policy
                                                    .billing_schedule)):
                months_after_eff_date = i*1
                bill_date = date_cursor + \
                    relativedelta(months=months_after_eff_date)
                invoice = Invoice(self.policy.id,
                                  bill_date,
                                  bill_date + relativedelta(months=1),
                                  bill_date + relativedelta(months=1, days=14),
                                  total_remaining /
                                  billing_schedules.get(self.policy
                                                            .billing_schedule))
                invoices.append(invoice)
        else:
            print "You have chosen a bad billing schedule."

        for invoice in invoices:
            db.session.add(invoice)
        db.session.commit()

################################
# The functions below are for the db and
# shouldn't need to be edited.
################################


def build_or_refresh_db():
    db.drop_all()
    db.create_all()
    insert_data()
    print "DB Ready!"


def insert_data():
    # Contacts
    contacts = []
    john_doe_agent = Contact('John Doe', 'Agent')
    contacts.append(john_doe_agent)
    john_doe_insured = Contact('John Doe', 'Named Insured')
    contacts.append(john_doe_insured)
    bob_smith = Contact('Bob Smith', 'Agent')
    contacts.append(bob_smith)
    anna_white = Contact('Anna White', 'Named Insured')
    contacts.append(anna_white)
    joe_lee = Contact('Joe Lee', 'Agent')
    contacts.append(joe_lee)
    ryan_bucket = Contact('Ryan Bucket', 'Named Insured')
    contacts.append(ryan_bucket)

    for contact in contacts:
        db.session.add(contact)
    db.session.commit()

    policies = []
    p1 = Policy('Policy One', date(2015, 1, 1), 365)
    p1.billing_schedule = 'Annual'
    p1.named_insured = john_doe_insured.id
    p1.agent = bob_smith.id
    policies.append(p1)

    p2 = Policy('Policy Two', date(2015, 2, 1), 1600)
    p2.billing_schedule = 'Quarterly'
    p2.named_insured = anna_white.id
    p2.agent = joe_lee.id
    policies.append(p2)

    p3 = Policy('Policy Three', date(2015, 1, 1), 1200)
    p3.billing_schedule = 'Monthly'
    p3.named_insured = ryan_bucket.id
    p3.agent = john_doe_agent.id
    policies.append(p3)

    p4 = Policy('Policy Four', date(2015, 2, 1), 500)
    p4.billing_schedule = 'Two-Pay'
    p4.named_insured = ryan_bucket.id
    p4.agent = john_doe_agent.id
    policies.append(p4)

    for policy in policies:
        db.session.add(policy)
    db.session.commit()

    for policy in policies:
        PolicyAccounting(policy.id)

    payment_for_p2 = Payment(p2.id, anna_white.id, 400, date(2015, 2, 1))
    db.session.add(payment_for_p2)
    db.session.commit()
