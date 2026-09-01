#!/usr/bin/env python3
"""Final mobile header & UI polish for Calibre-Web."""

LAYOUT_FILE = "/app/calibre-web-automated/cps/templates/layout.html"
import re

with open(LAYOUT_FILE, "r", encoding="utf-8") as f:
    layout = f.read()

# Refine header styles for perfect brand + grab button fit
header_styles = """
    <style id="cwa-grab-mobile-styles">
      .cwa-header-grab-btn {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
        color: #ffffff !important;
        font-weight: 700;
        font-size: 13px;
        padding: 5px 12px;
        border-radius: 18px;
        text-decoration: none !important;
        box-shadow: 0 2px 8px rgba(249, 115, 22, 0.4);
        position: absolute;
        top: 9px;
        right: 96px;
        z-index: 100;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
      }
      .cwa-header-grab-btn:hover {
        transform: scale(1.05);
        color: #ffffff !important;
        box-shadow: 0 4px 14px rgba(249, 115, 22, 0.6);
      }
      .cwa-mobile-fab {
        display: none;
      }
      @media (max-width: 768px) {
        .navbar-header {
          display: flex !important;
          align-items: center !important;
          justify-content: flex-start !important;
          height: 48px !important;
          width: calc(100vw - 90px) !important;
          margin: 0 !important;
          padding: 0 8px !important;
          position: relative !important;
        }
        body > div.navbar.navbar-default.navbar-static-top > div > div.navbar-header > a.navbar-brand {
          display: inline-block !important;
          max-width: 110px !important;
          font-size: 14px !important;
          font-weight: 700 !important;
          line-height: normal !important;
          height: auto !important;
          padding: 0 !important;
          margin: 0 8px 0 0 !important;
          overflow: hidden !important;
          text-overflow: ellipsis !important;
          white-space: nowrap !important;
          color: #f1f5f9 !important;
        }
        .cwa-header-grab-btn {
          position: static !important;
          display: inline-flex !important;
          align-items: center !important;
          gap: 4px !important;
          padding: 4px 9px !important;
          font-size: 11.5px !important;
          font-weight: 800 !important;
          border-radius: 12px !important;
          background: linear-gradient(135deg, #f97316 0%, #ea580c 100%) !important;
          color: #ffffff !important;
          box-shadow: 0 2px 6px rgba(249, 115, 22, 0.45) !important;
          white-space: nowrap !important;
          flex-shrink: 0 !important;
        }
        .cwa-mobile-fab {
          display: flex !important;
          align-items: center !important;
          justify-content: center !important;
          gap: 6px !important;
          position: fixed !important;
          bottom: 22px !important;
          right: 18px !important;
          background: linear-gradient(135deg, #f97316 0%, #ea580c 100%) !important;
          color: #ffffff !important;
          font-weight: 800 !important;
          font-size: 14px !important;
          padding: 11px 18px !important;
          border-radius: 28px !important;
          box-shadow: 0 4px 18px rgba(249, 115, 22, 0.6), 0 2px 6px rgba(0,0,0,0.4) !important;
          z-index: 99990 !important;
          cursor: pointer !important;
          user-select: none !important;
          -webkit-tap-highlight-color: transparent !important;
          transition: transform 0.12s ease !important;
        }
        .cwa-mobile-fab:active {
          transform: scale(0.93) !important;
        }
      }
      @media (max-width: 360px) {
        body > div.navbar.navbar-default.navbar-static-top > div > div.navbar-header > a.navbar-brand {
          max-width: 90px !important;
        }
        .cwa-header-grab-btn .cwa-grab-text {
          display: none;
        }
      }
    </style>
"""

layout = re.sub(r'<style id="cwa-grab-mobile-styles">.*?</style>', header_styles.strip(), layout, flags=re.DOTALL)

with open(LAYOUT_FILE, "w", encoding="utf-8") as f:
    f.write(layout)
print("Updated layout.html successfully.")
