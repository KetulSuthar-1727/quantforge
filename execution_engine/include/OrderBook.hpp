#pragma once
#include "Order.hpp"
#include <queue>
#include <vector>

class OrderBook {

  private:
    struct BuyComparator {
      bool operator()(
        const Order& a,
        const Order& b
      ) const {
        return a.price < b.price;
      }
    };

    struct SellComparator {
      bool operator()(
        const Order& a,
        const Order& b
      ) const {
        return a.price > b.price;
      }
    };
    std::priority_queue<Order, std::vector<Order>, BuyComparator> buy_orders;
    std::priority_queue<Order, std::vector<Order>, SellComparator> sell_orders;

  public:
    void addOrder(const Order& order);
    const Order& bestBid() const;
    const Order& bestAsk() const;
    void removeBestBid();
    void removeBestAsk();
    void updateBestBidQuantity(int quantity);
    void updateBestAskQuantity(int quantity);
    bool hasOrders() const;
  };

