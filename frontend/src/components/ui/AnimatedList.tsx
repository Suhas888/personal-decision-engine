"use client";
import React, { ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface AnimatedListProps {
  children: ReactNode[];
  className?: string;
}

export const AnimatedList = ({ children, className }: AnimatedListProps) => {
  return (
    <div className={className}>
      <AnimatePresence mode="popLayout">
        {React.Children.map(children, (child) => (
          <motion.div
            layout
            initial={{ opacity: 0, y: 10, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.95 }}
            transition={{ type: "spring", stiffness: 300, damping: 25 }}
          >
            {child}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
};
