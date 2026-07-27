import type { ReactNode } from "react";
import "../homepage.css";
import "../home-motion.css";
import "../reviews.css";
import "../hotline.css";
import "../chat.css";

export default function PublicRoute({ children }: { children: ReactNode }) {
  return children;
}
