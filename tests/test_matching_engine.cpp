
#include <cassert>
#include <cmath>
#include <iostream>

#include "Order.hpp"
#include "OrderBook.hpp"
#include "MatchingEngine.hpp"

void test_partial_fill() {
  OrderBook book;
  book.addOrder({1, "AAPL", OrderSide::BUY, 105.0, 10});
  book.addOrder({2, "AAPL", OrderSide::SELL, 101.0, 6});

  MatchingEngine engine(book);
  engine.match();

  const auto& trades = engine.getTradeHistory();

  assert(trades.size() == 1);
  assert(trades[0].symbol == "AAPL");
  assert(trades[0].quantity == 6);
  assert(std::abs(trades[0].price - 101.0) < 1e-9);

  assert(book.bestBid().quantity == 4);
  assert(std::abs(book.bestBid().price - 105.0) < 1e-9);
}

void test_non_crossing_orders() {
  OrderBook book;
  book.addOrder({1, "AAPL", OrderSide::BUY, 100.0, 10});
  book.addOrder({2, "AAPL", OrderSide::SELL, 105.0, 10});

  MatchingEngine engine(book);
  engine.match();

  assert(engine.getTradeHistory().empty());
  assert(std::abs(book.bestBid().price - 100.0) < 1e-9);
  assert(std::abs(book.bestAsk().price - 105.0) < 1e-9);
}

void test_exact_fill() {
  OrderBook book;
  book.addOrder({1, "AAPL", OrderSide::BUY, 105.0, 8});
  book.addOrder({2, "AAPL", OrderSide::SELL, 101.0, 8});

  MatchingEngine engine(book);
  engine.match();

  const auto& trades = engine.getTradeHistory();

  assert(trades.size() == 1);
  assert(trades[0].quantity == 8);
  assert(book.hasOrders() == false);
}

void test_multiple_matches() {
  OrderBook book;
  book.addOrder({1, "AAPL", OrderSide::BUY, 105.0, 10});
  book.addOrder({2, "AAPL", OrderSide::SELL, 101.0, 4});
  book.addOrder({3, "AAPL", OrderSide::SELL, 102.0, 6});

  MatchingEngine engine(book);
  engine.match();

  const auto& trades = engine.getTradeHistory();

  assert(trades.size() == 2);
  assert(trades[0].quantity == 4);
  assert(trades[1].quantity == 6);
  assert(book.hasOrders() == false);
}

void test_empty_sell_side() {
  OrderBook book;
  book.addOrder({1, "AAPL", OrderSide::BUY, 105.0, 10});

  MatchingEngine engine(book);
  engine.match();

  assert(engine.getTradeHistory().empty());
  assert(book.bestBid().quantity == 10);
}

void test_equal_price_matching() {
  OrderBook book;
  book.addOrder({1, "AAPL", OrderSide::BUY, 101.0, 5});
  book.addOrder({2, "AAPL", OrderSide::SELL, 101.0, 5});

  MatchingEngine engine(book);
  engine.match();

  const auto& trades = engine.getTradeHistory();

  assert(trades.size() == 1);
  assert(trades[0].quantity == 5);
  assert(std::abs(trades[0].price - 101.0) < 1e-9);
  assert(book.hasOrders() == false);
}

int main() {
  test_partial_fill();
  test_non_crossing_orders();
  test_exact_fill();
  test_multiple_matches();
  test_empty_sell_side();
  test_equal_price_matching();

  std::cout << "All matching engine tests passed.\n";
  return 0;
}
