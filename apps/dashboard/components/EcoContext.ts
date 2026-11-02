"use client";

import { createContext } from "react";

/** Energy-saving mode: smaller pages, rarer background checks. Provided by the dashboard. */
export const EcoContext = createContext(false);
