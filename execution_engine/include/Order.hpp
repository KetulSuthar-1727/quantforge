#pragma once
#include <string>

enum class OrderSide {
  BUY,
  SELL
};

struct Order
{
  int id;
  std::string symbol;
  OrderSide side;
  double price;
  int quantity;
};
