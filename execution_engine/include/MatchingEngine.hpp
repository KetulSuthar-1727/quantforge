#pragma once

#include "OrderBook.hpp"
#include "Trade.hpp"
#include <vector>

class MatchingEngine
{
private:
    OrderBook &order_book;
    std::vector<Trade> trade_history;

public:
    explicit MatchingEngine(OrderBook &order_book);

    void match();

    const std::vector<Trade> &getTradeHistory() const;
};