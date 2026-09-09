"use client";
import React from "react";
import { cn } from "../../lib/utils";

interface ShinyTextProps {
  text: string;
  className?: string;
  speed?: number;
}

export const ShinyText = ({ text, className, speed = 8 }: ShinyTextProps) => {
  return (
    <span
      className={cn(
        "text-transparent bg-clip-text inline-block",
        "bg-gradient-to-r from-neutral-500 via-white to-neutral-500",
        "bg-[length:200%_auto] animate-shiny-text",
        className
      )}
      style={{ animationDuration: `${speed}s` }}
    >
      {text}
    </span>
  );
};
