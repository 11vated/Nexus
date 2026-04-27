"""
Smart Calculator - Compound Interest & Loan Calculator
With support for:
- Simple & Compound Interest
- Monthly contributions
- Multiple compounding periods (daily, monthly, annually)
- Loan payments with extra payment scenarios
"""

from math import pow
from typing import Optional


class FinancialCalculator:
    """Advanced financial calculator with multiple calculation modes"""
    
    def __init__(self):
        self.name = "Smart Calculator v1.0"
        self.version = "1.0.0"
    
    def simple_interest(self, principal: float, rate: float, time: float) -> dict:
        """Calculate simple interest"""
        rate_decimal = rate / 100
        interest = principal * rate_decimal * time
        total = principal + interest
        return {
            "principal": principal,
            "rate": rate,
            "time": time,
            "interest": round(interest, 2),
            "total": round(total, 2),
            "formula": "I = P * r * t"
        }
    
    def compound_interest(self, principal: float, rate: float, time: float, 
                        compounds_per_year: int = 12) -> dict:
        """Calculate compound interest with configurable compounding"""
        rate_decimal = rate / 100
        amount = principal * pow(1 + rate_decimal / compounds_per_year, 
                                 compounds_per_year * time)
        interest = amount - principal
        
        compound_labels = {
            1: "annually",
            12: "monthly", 
            365: "daily",
            4: "quarterly",
            52: "weekly"
        }
        
        return {
            "principal": principal,
            "rate": rate,
            "time": time,
            "compounding": compound_labels.get(compounds_per_year, f"{compounds_per_year}x/year"),
            "compounds_per_year": compounds_per_year,
            "total": round(amount, 2),
            "interest": round(interest, 2),
            "formula": f"A = P(1 + r/{compounds_per_year})^(n*t)"
        }
    
    def future_value_with_monthly_contributions(self, monthly_contribution: float,
                                               annual_rate: float, years: int,
                                               compounds_per_year: int = 12) -> dict:
        """Calculate future value with monthly contributions (annuity)"""
        r = annual_rate / 100 / compounds_per_year
        n = compounds_per_year * years
        
        if r == 0:
            future_value = monthly_contribution * n
        else:
            future_value = monthly_contribution * ((pow(1 + r, n) - 1) / r)
        
        total_contributions = monthly_contribution * n
        interest_earned = future_value - total_contributions
        
        return {
            "monthly_contribution": monthly_contribution,
            "annual_rate": annual_rate,
            "years": years,
            "future_value": round(future_value, 2),
            "total_contributions": round(total_contributions, 2),
            "interest_earned": round(interest_earned, 2),
            "effective_rate": round(annual_rate, 2)
        }
    
    def loan_payment(self, principal: float, annual_rate: float, years: int) -> dict:
        """Calculate monthly loan payment (amortization)"""
        if annual_rate == 0:
            monthly_payment = principal / (years * 12)
            return {
                "principal": principal,
                "annual_rate": annual_rate,
                "years": years,
                "monthly_payment": round(monthly_payment, 2),
                "total_payment": round(principal, 2),
                "total_interest": 0
            }
        
        monthly_rate = annual_rate / 100 / 12
        num_payments = years * 12
        
        payment = principal * (monthly_rate * pow(1 + monthly_rate, num_payments)) / \
                 (pow(1 + monthly_rate, num_payments) - 1)
        
        total_payment = payment * num_payments
        total_interest = total_payment - principal
        
        return {
            "principal": principal,
            "annual_rate": annual_rate,
            "years": years,
            "monthly_payment": round(payment, 2),
            "total_payment": round(total_payment, 2),
            "total_interest": round(total_interest, 2)
        }
    
    def loan_with_extra_payments(self, principal: float, annual_rate: float, 
                              years: int, extra_monthly: float = 0,
                              extra_one_time: float = 0, 
                              one_time_year: int = 1) -> dict:
        """Calculate loan with extra payment scenarios"""
        base = self.loan_payment(principal, annual_rate, years)
        
        monthly_rate = annual_rate / 100 / 12
        num_payments = years * 12
        
        balance = principal
        months = 0
        total_interest = 0
        
        while balance > 0.01:
            months += 1
            if months > num_payments * 2:
                break
                
            interest = balance * monthly_rate
            principal_payment = base["monthly_payment"] - interest
            
            if extra_monthly > 0:
                principal_payment += extra_monthly
            
            if months == one_time_year * 12 and extra_one_time > 0:
                principal_payment += extra_one_time
            
            if principal_payment > balance:
                principal_payment = balance
            
            balance -= principal_payment
            total_interest += interest
            
            if months % 12 == 0:
                pass
        
        original_total = base["total_payment"]
        new_total = (base["monthly_payment"] * months) if months < num_payments else base["total_payment"]
        months_saved = num_payments - min(months, num_payments)
        
        return {
            **base,
            "extra_monthly": extra_monthly,
            "extra_one_time": extra_one_time,
            "actual_months": months,
            "actual_years": round(months / 12, 1),
            "interest_saved": round(total_interest - base["total_interest"], 2),
            "months_saved": max(0, months_saved),
            "new_total": round(min(months, num_payments) * base["monthly_payment"], 2)
        }
    
    def compare_investment_strategies(self, principal: float, monthly: float,
                                 rate: float, years: int) -> dict:
        """Compare investment at different compounding frequencies"""
        compounds = [
            (1, "annually"),
            (4, "quarterly"),
            (12, "monthly"),
            (365, "daily")
        ]
        
        results = []
        for compounds_per_year, label in compounds:
            result = self.compound_interest(principal, rate, years, compounds_per_year)
            with_contrib = self.future_value_with_monthly_contributions(
                monthly, rate, years, compounds_per_year
            )
            results.append({
                "compounding": label,
                "final_amount": result["total"],
                "with_monthly": with_contrib["future_value"]
            })
        
        return {
            "principal": principal,
            "monthly_contribution": monthly,
            "rate": rate,
            "years": years,
            "comparisons": results
        }
    
    def calculate_all(self, principal: float, rate: float, time: float,
                     monthly_contribution: float = 0, 
                     compounds: int = 12) -> dict:
        """Run all calculations at once"""
        simple = self.simple_interest(principal, rate, time)
        compound = self.compound_interest(principal, rate, time, compounds)
        future = self.future_value_with_monthly_contributions(
            monthly_contribution, rate, time, compounds
        ) if monthly_contribution > 0 else None
        loan = self.loan_payment(principal, rate, time)
        
        return {
            "calculator": self.name,
            "version": self.version,
            "simple_interest": simple,
            "compound_interest": compound,
            "future_value": future,
            "loan_payment": loan
        }


def demo():
    """Demo the calculator capabilities"""
    calc = FinancialCalculator()
    
    print("=" * 60)
    print("SMART CALCULATOR DEMO")
    print("=" * 60)
    
    # Example 1: $10,000 at 5% for 10 years
    print("\n[1] Compound Interest: $10,000 at 5% for 10 years")
    result = calc.compound_interest(10000, 5, 10, 12)
    print(f"    Total: ${result['total']:,.2f}")
    print(f"    Interest: ${result['interest']:,.2f}")
    print(f"    Compounding: {result['compounding']}")
    
    # Example 2: Monthly contributions
    print("\n[2] Monthly Contributions: $500/month at 7% for 20 years")
    result = calc.future_value_with_monthly_contributions(500, 7, 20, 12)
    print(f"    Future Value: ${result['future_value']:,.2f}")
    print(f"    Contributions: ${result['total_contributions']:,.2f}")
    print(f"    Interest Earned: ${result['interest_earned']:,.2f}")
    
    # Example 3: Loan payment
    print("\n[3] Loan: $200,000 at 6% for 30 years")
    result = calc.loan_payment(200000, 6, 30)
    print(f"    Monthly Payment: ${result['monthly_payment']:,.2f}")
    print(f"    Total Payment: ${result['total_payment']:,.2f}")
    print(f"    Total Interest: ${result['total_interest']:,.2f}")
    
    # Example 4: Loan with extra payments
    print("\n[4] Loan with Extra Payments: $200K at 6%, +$200 extra/month")
    result = calc.loan_with_extra_payments(200000, 6, 30, extra_monthly=200)
    print(f"    Original: {result['years']} years, ${result['total_payment']:,.2f}")
    print(f"    With Extra: {result['actual_years']:.1f} years, ${result['new_total']:,.2f}")
    print(f"    Interest Saved: ${result['interest_saved']:,.2f}")
    print(f"    Time Saved: {result['months_saved']} months")
    
    # Example 5: Compare strategies
    print("\n[5] Comparing Compounding Periods:")
    print(f"    $5,000 + $200/month at 8% for 25 years")
    comp = calc.compare_investment_strategies(5000, 200, 8, 25)
    for c in comp["comparisons"]:
        print(f"    {c['compounding']:>10}: ${c['with_monthly']:>12,.2f}")
    
    print("\n" + "=" * 60)
    print("Calculator ready for use!")
    print("=" * 60)


if __name__ == "__main__":
    demo()