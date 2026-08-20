import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider, Navigate } from "react-router-dom";
import "./index.css";

import Landing from "./pages/Landing.jsx";
import MascotSheet from "./pages/MascotSheet.jsx";
import UseCases from "./pages/UseCases.jsx";
import Pricing from "./pages/Pricing.jsx";
import Blog from "./pages/Blog.jsx";
import About from "./pages/About.jsx";
import Contact from "./pages/Contact.jsx";
import SignIn from "./pages/SignIn.jsx";
import SignUp from "./pages/SignUp.jsx";
import Console from "./pages/Console.jsx";
import Overview from "./pages/Overview.jsx";
import Live from "./pages/Live.jsx";
import Trace from "./pages/Trace.jsx";
import Bugs from "./pages/Bugs.jsx";
import Benchmark from "./pages/Benchmark.jsx";
import Setup from "./pages/Setup.jsx";
import { isAuthed } from "./lib/auth.js";

function Protected({ children }) {
  return isAuthed() ? children : <Navigate to="/signin" replace />;
}

// Apply saved theme before first paint.
const savedTheme = localStorage.getItem("gremlin-theme");
if (savedTheme) document.documentElement.dataset.theme = savedTheme;

const router = createBrowserRouter([
  { path: "/", element: <Landing /> },
  { path: "/use-cases", element: <UseCases /> },
  { path: "/pricing", element: <Pricing /> },
  { path: "/blog", element: <Blog /> },
  { path: "/about", element: <About /> },
  { path: "/contact", element: <Contact /> },
  { path: "/mascot", element: <MascotSheet /> },
  { path: "/signin", element: <SignIn /> },
  { path: "/signup", element: <SignUp /> },
  {
    path: "/app",
    element: <Protected><Console /></Protected>,
    children: [
      { index: true, element: <Overview /> },
      { path: "live", element: <Live /> },
      { path: "trace", element: <Trace /> },
      { path: "bugs", element: <Bugs /> },
      { path: "benchmark", element: <Benchmark /> },
      { path: "setup", element: <Setup /> },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
);
