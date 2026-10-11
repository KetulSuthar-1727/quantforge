#pragma once

#include <string>
#include "MatchingEngine.hpp"
#include "Order.hpp"
#include <unordered_set>

enum class OrderStatus {
  ACCEPTED,
  REJECTED
};

class ExecutionEngine {
private:
  OrderBook& order_book;
  MatchingEngine matching_engine;
  std::unordered_set<int> seen_order_ids;

  bool isValidOrder(const Order& order) const;

public:
  explicit ExecutionEngine(OrderBook& order_book);

  OrderStatus submitOrder(const Order& order);

  const std::vector<Trade>& getTradeHistory() const;
};
