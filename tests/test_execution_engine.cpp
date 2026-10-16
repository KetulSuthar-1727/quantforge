#include <cassert>
#include <iostream>
#include <limits>

#include "ExecutionEngine.hpp"


void test_valid_non_crossing_order() {
  OrderBook book;
  ExecutionEngine engine(book);

  assert(
      engine.submitOrder(
          {1, "AAPL", OrderSide::BUY, 100.0, 10}
      ) == OrderStatus::ACCEPTED
  );

  assert(book.bestBid().price == 100.0);
  assert(book.bestBid().quantity == 10);
  assert(engine.getTradeHistory().empty());
}


void test_invalid_order_is_rejected()
{
  OrderBook book;
  ExecutionEngine engine(book);

  engine.submitOrder({0, "AAPL", OrderSide::BUY, 100.0, 10});
  engine.submitOrder({2, "", OrderSide::BUY, 100.0, 10});
  engine.submitOrder({3, "AAPL", OrderSide::BUY, -1.0, 10});
  engine.submitOrder({4, "AAPL", OrderSide::BUY, 100.0, 0});

  assert(book.hasOrders() == false);
  assert(engine.getTradeHistory().empty());
  assert(
      engine.submitOrder(
          {0, "AAPL", OrderSide::BUY, 100.0, 10}) == OrderStatus::REJECTED);
}

void test_valid_orders_match()
{
  OrderBook book;
  ExecutionEngine engine(book);

  engine.submitOrder({1, "AAPL", OrderSide::BUY, 105.0, 10});
  engine.submitOrder({2, "AAPL", OrderSide::SELL, 101.0, 6});

  const auto &trades = engine.getTradeHistory();

  assert(trades.size() == 1);
  assert(trades[0].quantity == 6);
  assert(trades[0].price == 101.0);
  assert(book.bestBid().quantity == 4);
}


void test_duplicate_order_id_is_rejected() {
  OrderBook book;
  ExecutionEngine engine(book);

  assert(
      engine.submitOrder(
          {1, "AAPL", OrderSide::BUY, 100.0, 10}
      ) == OrderStatus::ACCEPTED
  );

  assert(
      engine.submitOrder(
          {1, "AAPL", OrderSide::SELL, 100.0, 10}
      ) == OrderStatus::REJECTED
  );

  assert(book.bestBid().quantity == 10);
  assert(engine.getTradeHistory().empty());
}

void test_non_finite_prices_are_rejected() {
  OrderBook book;
  ExecutionEngine engine(book);

  assert(
      engine.submitOrder({
          1, "AAPL", OrderSide::BUY,
          std::numeric_limits<double>::quiet_NaN(), 10
      }) == OrderStatus::REJECTED
  );

  assert(
      engine.submitOrder({
          2, "AAPL", OrderSide::BUY,
          std::numeric_limits<double>::infinity(), 10
      }) == OrderStatus::REJECTED
  );

  assert(book.hasOrders() == false);
}

void test_different_symbols_are_rejected() {
  OrderBook book;
  ExecutionEngine engine(book);

  assert(
      engine.submitOrder(
          {1, "AAPL", OrderSide::BUY, 105.0, 10}
      ) == OrderStatus::ACCEPTED
  );

  assert(
      engine.submitOrder(
          {2, "MSFT", OrderSide::SELL, 100.0, 10}
      ) == OrderStatus::REJECTED
  );

  assert(engine.getTradeHistory().empty());

  assert(book.bestBid().symbol == "AAPL");
  assert(book.bestBid().quantity == 10);
}

int main()
{
  test_valid_non_crossing_order();
  test_invalid_order_is_rejected();
  test_valid_orders_match();
  test_duplicate_order_id_is_rejected();
  test_non_finite_prices_are_rejected();
  test_different_symbols_are_rejected();

  std::cout << "All execution engine tests passed.\n";
  return 0;
}
