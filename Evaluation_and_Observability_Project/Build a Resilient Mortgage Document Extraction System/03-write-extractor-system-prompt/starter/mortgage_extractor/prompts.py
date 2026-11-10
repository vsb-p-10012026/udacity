"""System prompts, normalization rules, and few-shot examples.

The prompts in this module teach the extractor *how* to handle the cases the
schema alone cannot enforce: when to return null instead of fabricating, how to
normalize informal numerics, and how to record arithmetic discrepancies
verbatim rather than silently correcting them.

The single source of truth for normalization is :data:`NORMALIZATION_RULES`,
which is interpolated into every extractor system prompt and is the canonical
reference for the rules described in the module docstrings of
:mod:`mortgage_extractor.schema` and :mod:`mortgage_extractor.models`.
"""
from __future__ import annotations

from mortgage_extractor.models import DocumentType

# TODO: Build the NORMALIZATION_RULES constant as a single string. It must
# contain at minimum:
#   - the literal substring "Square footage" with an example like
#     "about 2,400 sq ft" → 2400
#   - the literal substring "Currency" with an example like "$485,000" → 485000.0
#   - the literal substring "Percentage" with an example like "6.5%" → 0.065
# The test in tests/test_us03_prompts.py::test_ac_03_05_normalization_rules_is_single_referenced_constant
# asserts those substrings, the "6.5%" / "0.065" pair, and the "2,400" / "2400" pair.
NORMALIZATION_RULES = (
    "Normalization guidelines:\n"
    "- Square footage: extract numeric integer values from expressions like 'about 2,400 sq ft' -> 2400.\n"
    "- Currency: extract numeric float or integer values from currency strings like '$485,000' -> 485000.0.\n"
    "- Percentage: extract decimal values from percentages like '6.5%' -> 0.065."
) # TODO: replace with the rule text

# TODO: Build the _CATEGORICAL_CRITERIA constant as a numbered list of at
# least four rules. The FIRST item must be, VERBATIM:
#
#     1. Return null for any field not explicitly stated in the document. Do not infer, default, or fabricate.
#
# (This exact substring must appear as item 1.) The remaining
# items should distinguish base income from bonus, commission, and overtime;
# tell the model to emit "other" + *_detail when an enum doesn't fit; and
# remind the model that numeric fields receive numbers, not strings.
_CATEGORICAL_CRITERIA = (
    "1. Return null for any field not explicitly stated in the document. Do not infer, default, or fabricate.\n"
    "2. Distinguish base monthly income clearly from bonus, commission, and overtime earnings.\n"
    "3. When a categorical enum value does not fit the document, emit 'other' and provide the description in the sibling *_detail field.\n"
    "4. Ensure all numeric fields receive proper numeric types (integers or floats), never raw strings."
)  # TODO: replace with the numbered criteria block

# TODO: Build the _FEW_SHOT_EXAMPLES constant as a single string containing
# EXACTLY FOUR <example> blocks. Each block has this shape:
#
#     <example name="<short-name>">
#     <input>
#     ...document excerpt...
#     </input>
#     <reasoning>
#     ...explanation of WHY the chosen output is correct vs. the plausible
#     alternative...
#     </reasoning>
#     <output>
#     ...JSON output...
#     </output>
#     </example>
#
# Four examples are required, whose names contain (in some order):
#   - "clean"     — a fully-populated paystub where every component is stated
#   - "missing"   — a paystub that does not mention bonus; bonus_monthly is null
#   - "informal"  — an appraisal saying "about 2,400 sq ft"; sqft is 2400 (int)
#   - "mismatch"  — a paystub whose stated total doesn't equal the line-item sum
#
# Each example must contain an inline <reasoning>...</reasoning>
# block explaining the choice — for instance, for "missing":
# "bonus_ytd is null because the document says no bonus this year — fabricating
# a zero would imply zero earned, not zero reported."
_FEW_SHOT_EXAMPLES = """
<example name="clean-paystub">
<input>
Borrower: Jane Doe
Employer: Acme Corp
Base Monthly: $5,000.00
Bonus YTD: $1,200.00
Commission YTD: $0.00
</input>
<reasoning>
Every field is explicitly and clearly stated in the document, so all values are populated directly with no missing or ambiguous data.
</reasoning>
<output>
{
  "borrower": {
    "full_name": "Jane Doe",
    "coborrower_name": null,
    "credit_score": null,
    "ssn_last_four": null
  },
  "property": {
    "address": null,
    "property_type": null,
    "property_type_detail": null,
    "occupancy_type": null,
    "occupancy_type_detail": null,
    "year_built": null,
    "hoa_dues_monthly": null
  },
  "loan": {
    "amount": null,
    "loan_purpose": null,
    "loan_purpose_detail": null,
    "interest_rate": null,
    "term_months": null
  },
  "income": {
    "base_monthly": 5000.0,
    "bonus_ytd": 1200.0,
    "commission_ytd": 0.0,
    "employer_name": "Acme Corp"
  }
}
</output>
</example>

<example name="missing-bonus">
<input>
Borrower: John Smith
Employer: Beta LLC
Base Monthly: $4,500.00
Bonus: None reported for this period.
</input>
<reasoning>
bonus_ytd is null because the document says no bonus this year — fabricating a zero would imply zero earned, not zero reported.
</reasoning>
<output>
{
  "borrower": {
    "full_name": "John Smith",
    "coborrower_name": null,
    "credit_score": null,
    "ssn_last_four": null
  },
  "property": {
    "address": null,
    "property_type": null,
    "property_type_detail": null,
    "occupancy_type": null,
    "occupancy_type_detail": null,
    "year_built": null,
    "hoa_dues_monthly": null
  },
  "loan": {
    "amount": null,
    "loan_purpose": null,
    "loan_purpose_detail": null,
    "interest_rate": null,
    "term_months": null
  },
  "income": {
    "base_monthly": 4500.0,
    "bonus_ytd": null,
    "commission_ytd": null,
    "employer_name": "Beta LLC"
  }
}
</output>
</example>

<example name="informal-appraisal">
<input>
Property Address: 742 Evergreen Terrace
Property Type: about 2,400 sq ft single family dwelling
</input>
<reasoning>
Square footage and informal descriptions are normalized to structured numeric integers where applicable, and property type maps to valid enums.
</reasoning>
<output>
{
  "borrower": {
    "full_name": null,
    "coborrower_name": null,
    "credit_score": null,
    "ssn_last_four": null
  },
  "property": {
    "address": "742 Evergreen Terrace",
    "property_type": "single_family",
    "property_type_detail": null,
    "occupancy_type": null,
    "occupancy_type_detail": null,
    "year_built": null,
    "hoa_dues_monthly": null
  },
  "loan": {
    "amount": null,
    "loan_purpose": null,
    "loan_purpose_detail": null,
    "interest_rate": null,
    "term_months": null
  },
  "income": {
    "base_monthly": null,
    "bonus_ytd": null,
    "commission_ytd": null,
    "employer_name": null
  }
}
</output>
</example>

<example name="mismatch-paystub">
<input>
Borrower: Alice Johnson
Stated Gross Pay: $6,000.00
Base Salary: $5,000.00
(Note: line items sum to $5,000 but stated gross is $6,000 due to unlisted retroactive adjustment)
</input>
<reasoning>
Arithmetic discrepancies are recorded verbatim from the document text rather than silently overriding or correcting reported totals.
</reasoning>
<output>
{
  "borrower": {
    "full_name": "Alice Johnson",
    "coborrower_name": null,
    "credit_score": null,
    "ssn_last_four": null
  },
  "property": {
    "address": null,
    "property_type": null,
    "property_type_detail": null,
    "occupancy_type": null,
    "occupancy_type_detail": null,
    "year_built": null,
    "hoa_dues_monthly": null
  },
  "loan": {
    "amount": null,
    "loan_purpose": null,
    "loan_purpose_detail": null,
    "interest_rate": null,
    "term_months": null
  },
  "income": {
    "base_monthly": 5000.0,
    "bonus_ytd": null,
    "commission_ytd": null,
    "employer_name": null
  }
}
</output>
</example>
"""  # TODO: replace with the four <example> blocks


def classifier_system_prompt() -> str:
    """System prompt for the classifier pass.

    Provided as-is — the classifier prompt isn't load-bearing for Exercise 3's
    LO. (You wrote and tested this in Exercise 2 against the placeholder
    extractor prompts; the rules above don't apply to classify.)
    """
    return (
        "You are a document classifier for a mortgage lender. You will receive "
        "the text of a single mortgage-related document and must call the "
        "`classify_document` tool exactly once with the document's type and a "
        "one-sentence reason describing the textual cues that drove the "
        "classification. Use `other` if the document is not one of the listed "
        "types or is too damaged to classify confidently."
    )


def extractor_system_prompt(doc_type: DocumentType) -> str:
    """Return the system prompt for the given document type's extractor.

    All extractor prompts share the same normalization rules and few-shot
    examples; the income-verification prompt additionally surfaces the full
    explicit categorical criteria block.
    """
    # TODO: Assemble the extractor system prompt for non-income document types
    # (LOAN_APPLICATION, APPRAISAL):
    #   1. If doc_type is INCOME_VERIFICATION, delegate to
    #      income_verification_system_prompt() and return.
    #   2. Otherwise, return:
    #        intro + NORMALIZATION_RULES + "\n" + _FEW_SHOT_EXAMPLES
    #      where `intro` is a 2-3 sentence instruction that names the
    #      doc_type, tells the model to call extract_<doc_type> exactly once
    #      with the structured data, and offer `flag_for_review` if the
    #      document is unreadable.
    if doc_type == DocumentType.INCOME_VERIFICATION or doc_type == "income_verification":
        return income_verification_system_prompt()

    doc_name = doc_type.value if hasattr(doc_type, "value") else str(doc_type)
    intro = (
        f"You are a specialized mortgage extractor for a {doc_name} document. "
        f"Call the extract_{doc_name} tool exactly once with the structured data, "
        "or call flag_for_review if the document is unreadable."
    )
    return intro + "\n\n" + NORMALIZATION_RULES + "\n" + _FEW_SHOT_EXAMPLES

def income_verification_system_prompt() -> str:
    """Return the income-verification extractor system prompt.

    This is the canonical extractor prompt: it contains the verbatim null-
    handling criterion as item #1, four numbered categorical criteria, the
    shared :data:`NORMALIZATION_RULES`, and four contrastive few-shot examples
    each with an inline ``<reasoning>`` block.
    """
    # TODO: Assemble the income-verification prompt by concatenating:
    #   1. A short intro (2-3 sentences) naming the document type and telling
    #      the model to call extract_income_verification exactly once or
    #      flag_for_review if the document is unreadable.
    #   2. _CATEGORICAL_CRITERIA (the four numbered rules).
    #   3. A blank line.
    #   4. NORMALIZATION_RULES.
    #   5. A blank line.
    #   6. _FEW_SHOT_EXAMPLES (the four <example> blocks).
    intro = (
        "You are a specialized mortgage extractor for an income_verification document. "
        "Call the extract_income_verification tool exactly once with the extracted structured data, "
        "or call flag_for_review if the document is unreadable."
    )
    return intro + "\n\n" + _CATEGORICAL_CRITERIA + "\n\n" + NORMALIZATION_RULES + "\n\n" + _FEW_SHOT_EXAMPLES