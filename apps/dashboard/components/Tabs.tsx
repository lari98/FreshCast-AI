"use client";

import { useRef } from "react";
import type { KeyboardEvent, ReactNode } from "react";

export interface TabDef {
  id: string;
  label: string;
}

export interface TabGroup {
  label: string;
  tabs: TabDef[];
}

interface Props {
  groups: TabGroup[];
  active: string;
  onChange: (id: string) => void;
  label: string;
  children: ReactNode;
}

/**
 * Accessible tabs (WAI-ARIA tabs pattern) with grouped navigation: a sidebar on
 * wide screens, a scrolling bar on narrow ones. One tab stop, arrow keys,
 * Home/End. Only the active panel is rendered.
 */
export function Tabs({ groups, active, onChange, label, children }: Props) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const flat = groups.flatMap((g) => g.tabs);

  function onKeyDown(event: KeyboardEvent, index: number) {
    const last = flat.length - 1;
    const forward = event.key === "ArrowRight" || event.key === "ArrowDown";
    const back = event.key === "ArrowLeft" || event.key === "ArrowUp";
    const next =
      forward ? (index === last ? 0 : index + 1)
      : back ? (index === 0 ? last : index - 1)
      : event.key === "Home" ? 0
      : event.key === "End" ? last
      : null;
    if (next === null) return;
    event.preventDefault();
    const target = flat[next];
    if (!target) return;
    onChange(target.id);
    refs.current[target.id]?.focus();
  }

  return (
    <div className="shell">
      <div role="tablist" aria-label={label} aria-orientation="vertical" className="tabs">
        {groups.map((group) => (
          <div key={group.label} role="presentation" className="tab-group">
            <span role="presentation" className="tab-group-label" aria-hidden="true">
              {group.label}
            </span>
            {group.tabs.map((tab) => {
              const index = flat.indexOf(tab);
              return (
                <button
                  key={tab.id}
                  ref={(el) => {
                    refs.current[tab.id] = el;
                  }}
                  type="button"
                  role="tab"
                  id={`tab-${tab.id}`}
                  aria-selected={tab.id === active}
                  aria-controls={`panel-${tab.id}`}
                  tabIndex={tab.id === active ? 0 : -1}
                  className="tab"
                  onClick={() => onChange(tab.id)}
                  onKeyDown={(e) => onKeyDown(e, index)}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
        ))}
      </div>
      <div role="tabpanel" id={`panel-${active}`} aria-labelledby={`tab-${active}`} tabIndex={0} className="panel">
        {children}
      </div>
    </div>
  );
}
