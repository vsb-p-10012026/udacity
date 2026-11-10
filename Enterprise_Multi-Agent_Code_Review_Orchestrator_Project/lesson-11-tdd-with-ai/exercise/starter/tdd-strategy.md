# TDD Strategy for Shopping Cart Module

## 1. Requirements Specifications

Write natural language requirements that Claude can convert to tests.

### 1.1 Add Item to Cart

<!-- TODO: Write requirements for adding items to cart -->
<!-- Include: inputs, outputs, validation rules, error conditions -->

**Requirement:**Allow a user to add a specified product and quantity to their active shopping cart. If the product already exists in the cart, increment its quantity rather than creating a duplicate entry.

**Inputs:**
- productId (string, required)
- quantity (integer, default: 1)
- price (number, required)
- variantId (string, optional)

**Expected Output:**An updated Cart object containing the updated item list, total item count, and recalculated subtotal.

**Validation Rules:**
- quantity must be a positive integer greater than 0.
- productId must be a non-empty string.
- Requested quantity must not exceed available product stock.

**Error Conditions:**
- Throws ValidationError if quantity <= 0 or productId is missing.
- Throws  OutOfStockError if the requested quantity exceeds inventory levels.
---

### 1.2 Remove Item from Cart

<!-- TODO: Write requirements for removing items from cart -->

**Requirement:**Remove an item entirely from the shopping cart based on its product ID and optional variant ID.

**Inputs:**
- productId (string, required)
- variantId (string, optional)

**Expected Output:**An updated Cart object with the target item removed and cart totals recalculated.

**Validation Rules:**
- productId must reference an item currently present in the active cart state.

**Error Conditions:**
- Throws ItemNotFoundError if the product/variant combination does not exist in the cart.

---

### 1.3 Update Item Quantity

<!-- TODO: Write requirements for updating item quantities -->

**Requirement:**Update the quantity of an existing cart item to a new absolute value. If the new quantity is set to zero, the item should be automatically removed.

**Inputs:**
- productId (string, required)
- newQuantity (integer, required)
- variantId (string, optional)

**Expected Output:**An updated Cart object reflecting the new quantity, item-level subtotal, and cart totals.

**Validation Rules:**
- newQuantity must be greater than or equal to 0.
- newQuantity must not exceed available stock.

**Error Conditions:**
- Throws ItemNotFoundError if the item is not found in the cart.
- Throws ValidationError if newQuantity is negative or exceeds available inventory.

---

### 1.4 Apply Promotional Code

<!-- TODO: Write requirements for promotional codes -->
<!-- Consider: code types, restrictions, expiration -->

**Requirement:**Apply a promotional discount code to the cart to reduce the order subtotal according to the promotion rules (percentage or fixed discount).

**Inputs:**
- promoCode (string, required)

**Expected Output:**An updated Cart object with the discount applied, showing the discount amount and recalculated total.

**Validation Rules:**
- The promo code must exist in the database, be active, and not be expired.
- The cart subtotal must meet any minimum spend requirements associated with the code.

**Error Conditions:**
- Throws InvalidPromoError if the code is unrecognized.
- Throws ExpiredPromoError if the code has passed its expiration date.
- Throws PromoMinSpendNotMetError if the cart subtotal is lower than the required threshold.

---

### 1.5 Calculate Total with Tax

<!-- TODO: Write requirements for total calculation -->
<!-- Consider: subtotal, discounts, tax rates, rounding -->

**Requirement:**Compute the final checkout total by aggregating subtotal, discounts, shipping fees, and regional tax rates, with precise currency rounding.

**Inputs:**
- shippingAddress (object containing country and state/province, required)
- taxRateOverride (number, optional)

**Expected Output:**A detailed cost breakdown object containing subtotal, discountTotal, shippingFee, taxTotal, and finalTotal rounded to 2 decimal places.

**Validation Rules:**
- Tax rates must be dynamically resolved based on the shipping destination jurisdiction.
- All calculations must use integer-based cents internally to avoid floating-point drift.

**Error Conditions:**
- Throws InvalidAddressError if the shipping jurisdiction is missing or invalid for tax calculation.
---

## 2. Edge Cases AI Might Miss

List edge cases that require human domain knowledge. These are scenarios AI wouldn't automatically consider without business context.

<!-- TODO: List at least 5 edge cases -->

| # | Edge Case | Why AI Might Miss It | How to Test |
|---|-----------|---------------------|-------------|
| 1 | Floating-point precision errors during percentage discount calculations (e.g., $19.99 * 15% off). | AI typically uses native JavaScript floating-point arithmetic (0.1 + 0.2 != 0.3). | Assert exact integer-cent rounding or decimal library outputs. |
| 2 | Concurrent inventory mutation where stock drops to zero while an item sits in an active cart. | AI writes unit tests assuming static mock data rather than dynamic race conditions. | Mock inventory lock service failures and verify cart validation handling. |
| 3 | Timezone mismatches for promo expiration (UTC vs. user local time causing codes to expire prematurely). | AI assumes standard naive date comparisons without timezone normalization. | Mock system clocks across diverse UTC offsets. |
| 4 | Guest cart merging upon login with a pre-existing saved user cart containing duplicate items. | AI focuses on single-session state mutations, missing cross-session ID mapping and collision rules. | Test merge scenarios where identical items combine quantities up to stock limits. |
| 5 | Subtotal recalculation after item quantity reduction invalidates an applied promo code's minimum spend. | AI tests promo application once, missing reactive validation when cart state changes post-application. | Apply promo, reduce item quantity below minimum spend, and verify promo auto-removal. |

---

## 3. Coverage Targets

Define your coverage goals and explain the rationale.

<!-- TODO: Set coverage targets -->

| Metric | Target | Rationale |
|--------|--------|-----------|
| Line Coverage | 95% | Ensures almost all execution pathways are exercised during automated test suites. |
| Branch Coverage | 90% | Ensures all conditional branches (error handlers, promo checks, tax rules) are explicitly tested. |
| Function Coverage | 100% | Every public method and domain utility helper must have at least one dedicated test. |

**Areas Requiring 100% Coverage:**
<!-- List critical paths that must have complete coverage -->
- Currency arithmetic and rounding logic.
- Promotional code validation rules (expiration, minimum spend, percentage vs. fixed).
- Inventory stock threshold validation.

**Areas Where Lower Coverage is Acceptable:**
<!-- List areas where exhaustive testing isn't cost-effective -->
- Framework boilerplate wrappers and passive type definitions.
- Generic logging and telemetry instrumentation hooks.
---

## 4. Red-Green-Refactor Sequence

Plan the order of test implementation and code development.

<!-- TODO: Define the implementation sequence -->

### Phase 1: Core Functionality (Red-Green)

| Step | Test to Write | Implementation Needed |
|------|---------------|----------------------|
| 1 | cart.spec.ts: Should add a new item and calculate subtotal | Implement Cart class structure and addItem() method |
| 2 | cart.spec.ts: Should increment quantity if item already exists | Update addItem() to check for existing product/variant keys |
| 3 | cart.spec.ts: Should remove an item and update cart totals | Implement removeItem() method |

### Phase 2: Edge Cases (Red-Green)

| Step | Test to Write | Implementation Needed |
|------|---------------|----------------------|
| 1 | cart.spec.ts: Should throw OutOfStockError when quantity exceeds stock | Add inventory validation check inside addItem() and updateQuantity() |
| 2 | cart.spec.ts: Should auto-remove item when updated quantity is zero | Handle zero/negative quantity bounds in updateQuantity() |
| 3 | promo.spec.ts: Should reject expired promotional codes | Implement date-comparison validation in promo service |

### Phase 3: Refactoring

| Refactoring | Before | After | Tests Must Still Pass |
|-------------|--------|-------|----------------------|
| Extract Currency Utility | Inline float math in cart totals | Dedicated Money value object handling integer cents | All cart calculation and tax tests |
| Abstract Inventory Validator | Direct stock array lookup | Interface-based InventoryRepository dependency injection | Add/Update item tests |

---

## 5. Validation Checklist for AI-Generated Tests

How will you verify that tests Claude generates are correct and complete?

<!-- TODO: Create a checklist -->

### Test Quality Checks

- [ ] Are test descriptions (it(...)) clear and behavior-driven (e.g., "should throw error when..." instead of "tests error")?
- [ ] Are mocks and stubs properly reset in beforeEach to prevent test pollution?
- [ ] Are assertions isolated so that a single test failure points to a specific broken behavior?
- [ ] Are asynchronous tests correctly awaiting promises or returning async assertions?
- [ ] Are TypeScript types strict without relying on unjustified any assertions?

### Business Logic Verification

- [ ] Do tests cover boundary conditions (e.g., quantity = 0, exact minimum spend threshold)?
- [ ] Are currency calculations verified against rounding edge cases (half-up rounding)?
- [ ] Are unauthorized state changes explicitly blocked and tested?

### Security Considerations

- [ ] Are cart payloads protected against prototype pollution vectors?
- [ ] Are promotional code inputs sanitized against injection or malformed payloads?

---

## 6. Sample AI-Generated Test

Use Claude Code to generate at least one test based on your requirements, and paste it here.

**Prompt Used:**
```
<!-- Paste the prompt you gave Claude -->
Write a Jest test for the ShoppingCart module that verifies adding an item with valid stock updates the subtotal correctly, and throws an OutOfStockError if the requested quantity exceeds available inventory.
```

**Generated Test:**
```typescript
// TODO: Paste the test Claude generated here
import { ShoppingCart } from '../src/cart';
import { OutOfStockError } from '../src/errors';

describe('ShoppingCart - Add Item', () => {
  let cart: ShoppingCart;
  let mockInventoryService: any;

  beforeEach(() => {
    mockInventoryService = {
      getStockLevel: jest.fn().mockResolvedValue(5),
    };
    cart = new ShoppingCart(mockInventoryService);
  });

  it('should add an item successfully and update subtotal when stock is sufficient', async () => {
    const item = { productId: 'prod-123', price: 10.00, quantity: 2 };
    
    await cart.addItem(item);

    expect(cart.getItems()).toHaveLength(1);
    expect(cart.getSubtotal()).toBe(20.00);
  });

  it('should throw OutOfStockError when requested quantity exceeds inventory', async () => {
    const item = { productId: 'prod-123', price: 10.00, quantity: 10 };

    await expect(cart.addItem(item)).rejects.toThrow(OutOfStockError);
    expect(cart.getItems()).toHaveLength(0);
  });
});
```

**Your Assessment:**
<!-- Did Claude capture the requirement correctly? What would you add or change? -->
Claude captured the requirement accurately, including async inventory verification and proper assertion patterns (rejects.toThrow). Improvement: Ensure mock dependency injection is clearly separated and that currency values are handled using integer cents internally to avoid floating-point drift in subsequent calculations.
---

## Summary

<!-- After completing all sections, write a brief summary of your TDD strategy -->

**Key Decisions:**
- Using integer-based arithmetic (cents) internally for all monetary calculations to eliminate floating-point drift.
- Abstracting inventory checks behind an injectable interface to allow clean unit testing without external database dependencies.

**Biggest Risks:**
- Handling concurrent stock reductions during active user checkouts.
- Promo code stacking rules causing negative cart totals if validation bounds are missed.

**Where Human Judgment is Essential:**
- Defining complex promotional discount priority rules (e.g., whether category-level discounts stack with cart-wide percentage codes).
- Establishing tax jurisdiction fallback logic for international shipping destinations.
