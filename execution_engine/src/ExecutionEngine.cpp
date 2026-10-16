#include <cmath>
#include "ExecutionEngine.hpp"

ExecutionEngine::ExecutionEngine(OrderBook& order_book)
    : order_book(order_book),
      matching_engine(order_book) {
}

bool ExecutionEngine::isValidOrder(const Order& order) const {
  return order.id > 0 &&
         !order.symbol.empty() &&
         order.price > 0.0 &&
         std::isfinite(order.price) &&
         order.quantity > 0;
}

OrderStatus ExecutionEngine::submitOrder(const Order& order) {
  if (!isValidOrder(order)) {
    return OrderStatus::REJECTED;
  }

  if (seen_order_ids.count(order.id) > 0) {
    return OrderStatus::REJECTED;
  }

  if (!active_symbol.empty() && order.symbol != active_symbol) {
    return OrderStatus::REJECTED;
  }

  if (active_symbol.empty()) {
    active_symbol = order.symbol;
  }

  seen_order_ids.insert(order.id);

  order_book.addOrder(order);
  matching_engine.match();

  return OrderStatus::ACCEPTED;
}

const std::vector<Trade>& ExecutionEngine::getTradeHistory() const {
  return matching_engine.getTradeHistory();
}
