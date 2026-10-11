#include <iostream>
#include "../include/MatchingEngine.hpp"
#include "../include/OrderBook.hpp"

int main()
{

  OrderBook order_book;

  Order buy_1{
      1,
      "AAPL",
      OrderSide::BUY,
      98.0,
      10};

  Order buy_2{
      2,
      "AAPL",
      OrderSide::BUY,
      105.0,
      10};

  Order buy_3{
      3,
      "AAPL",
      OrderSide::BUY,
      100.0,
      10};

  Order sell_1{
      4,
      "AAPL",
      OrderSide::SELL,
      103.0,
      10};

  Order sell_2{
      5,
      "AAPL",
      OrderSide::SELL,
      101.0,
      10};

  Order sell_3{
      6,
      "AAPL",
      OrderSide::SELL,
      105.0,
      10};

  order_book.addOrder(buy_1);
  order_book.addOrder(buy_2);
  order_book.addOrder(buy_3);

  order_book.addOrder(sell_1);
  order_book.addOrder(sell_2);
  order_book.addOrder(sell_3);

  MatchingEngine matching_engine(order_book);

  matching_engine.match();

  const auto &trades = matching_engine.getTradeHistory();

  std::cout << "\nTrade History:\n";

  for (const auto &trade : trades)
  {
    std::cout << trade.symbol
              << " | Quantity: " << trade.quantity
              << " | Price: " << trade.price
              << '\n';
  }

  std::cout << "Best Bid: "
            << order_book.bestBid().price
            << '\n';

  std::cout << "Best Ask: "
            << order_book.bestAsk().price
            << '\n';

  return 0;
}