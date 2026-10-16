#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "ExecutionEngine.hpp"
#include "OrderBook.hpp"
#include "Order.hpp"
#include "Trade.hpp"

namespace py = pybind11;

PYBIND11_MODULE(quantforge_cpp, m)
{
  py::enum_<OrderSide>(m, "OrderSide")
      .value("BUY", OrderSide::BUY)
      .value("SELL", OrderSide::SELL);

  py::enum_<OrderStatus>(m, "OrderStatus")
      .value("ACCEPTED", OrderStatus::ACCEPTED)
      .value("REJECTED", OrderStatus::REJECTED);

  py::class_<Order>(m, "Order")
      .def(py::init<int, std::string, OrderSide, double, int>())
      .def_readwrite("id", &Order::id)
      .def_readwrite("symbol", &Order::symbol)
      .def_readwrite("side", &Order::side)
      .def_readwrite("price", &Order::price)
      .def_readwrite("quantity", &Order::quantity);

  py::class_<Trade>(m, "Trade")
      .def_readonly("symbol", &Trade::symbol)
      .def_readonly("quantity", &Trade::quantity)
      .def_readonly("price", &Trade::price);

  py::class_<OrderBook>(m, "OrderBook")
      .def(py::init<>());

  py::class_<ExecutionEngine>(m, "ExecutionEngine")
      .def(py::init<OrderBook &>())
      .def("submit_order", &ExecutionEngine::submitOrder)
      .def("get_trade_history",
           &ExecutionEngine::getTradeHistory,
           py::return_value_policy::copy);
}