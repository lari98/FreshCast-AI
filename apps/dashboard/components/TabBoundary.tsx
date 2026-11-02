"use client";

import { Component } from "react";
import type { ReactNode } from "react";
import type { Strings } from "@/lib/i18n";

interface Props {
  t: Strings;
  /** Changing this (the active tab) clears an earlier error, so one broken tab never blocks the others. */
  resetKey: string;
  children: ReactNode;
}

/**
 * Keeps a rendering error in one tab from blanking the whole dashboard. The error is
 * not shown in detail (it could echo uploaded content); the user can retry or switch tab.
 */
export class TabBoundary extends Component<Props, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidUpdate(prev: Props) {
    if (prev.resetKey !== this.props.resetKey && this.state.failed) this.setState({ failed: false });
  }

  render() {
    if (!this.state.failed) return this.props.children;
    const { t } = this.props;
    return (
      <section className="card" role="alert">
        <h2>{t.errTitle}</h2>
        <p>{t.errBody}</p>
        <button type="button" className="btn" onClick={() => this.setState({ failed: false })}>{t.errRetry}</button>
      </section>
    );
  }
}
