#include "../include/MatchingEngine.hpp"
#include <algorithm>
#include <iostream>

MatchingEngine::MatchingEngine(OrderBook &order_book) : order_book(order_book)
{
}

void MatchingEngine::match()
{

    while (order_book.hasOrders())
    {

        if (order_book.bestBid().price <
            order_book.bestAsk().price)
        {
            break;
        }

        const Order buy_order = order_book.bestBid();
        const Order sell_order = order_book.bestAsk();

        int trade_quantity = std::min(
            buy_order.quantity,
            sell_order.quantity);

        double trade_price = sell_order.price;

        trade_history.push_back({buy_order.symbol,
                                 trade_quantity,
                                 trade_price});

        std::cout << "TRADE | "
                  << buy_order.symbol
                  << " | Quantity: " << trade_quantity
                  << " | Price: " << trade_price
                  << '\n';

        if (buy_order.quantity > sell_order.quantity)
        {

            order_book.updateBestBidQuantity(
                buy_order.quantity - trade_quantity);

            order_book.removeBestAsk();
        }
        else if (sell_order.quantity > buy_order.quantity)
        {

            order_book.updateBestAskQuantity(
                sell_order.quantity - trade_quantity);

            order_book.removeBestBid();
        }
        else
        {

            order_book.removeBestBid();
            order_book.removeBestAsk();
        }
    }
}

const std::vector<Trade>& MatchingEngine::getTradeHistory() const {
    return trade_history;
}