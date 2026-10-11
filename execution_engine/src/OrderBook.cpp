#include "../include/OrderBook.hpp"

void OrderBook::addOrder(const Order &order)
{

  if (order.side == OrderSide::BUY)
  {
    buy_orders.push(order);
  }
  else
  {
    sell_orders.push(order);
  }
}

const Order &OrderBook::bestBid() const
{
  return buy_orders.top();
}

const Order &OrderBook::bestAsk() const
{
  return sell_orders.top();
}

void OrderBook::removeBestBid()
{
  buy_orders.pop();
}

void OrderBook::removeBestAsk()
{
  sell_orders.pop();
}

void OrderBook::updateBestBidQuantity(int quantity)
{
  Order order = buy_orders.top();
  buy_orders.pop();

  order.quantity = quantity;

  buy_orders.push(order);
}

void OrderBook::updateBestAskQuantity(int quantity)
{
  Order order = sell_orders.top();
  sell_orders.pop();

  order.quantity = quantity;

  sell_orders.push(order);
}

bool OrderBook::hasOrders() const
{
  return !buy_orders.empty() && !sell_orders.empty();
}