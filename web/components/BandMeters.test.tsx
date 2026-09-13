import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { bar, part } from "@/lib/testing/fixtures";
import { PLAYER } from "@/lib/palette";
import { BandMeters } from "./BandMeters";

describe("BandMeters", () => {
  it("lists every player even when the bar is empty", () => {
    render(<BandMeters bar={null} />);

    for (const { name } of Object.values(PLAYER)) {
      expect(screen.getByText(name)).toBeDefined();
    }
  });

  it("describes who is playing for screen readers", () => {
    render(<BandMeters bar={bar(0, { flute: part("flute", [72, 74]) })} />);

    expect(screen.getByLabelText("Flute, 2 notes this bar")).toBeDefined();
    expect(screen.getByLabelText("Drums, not playing this bar")).toBeDefined();
  });

  it("marks the soloist", () => {
    render(<BandMeters bar={bar(0)} soloist="violin" />);

    expect(screen.getByText("solo")).toBeDefined();
  });

  it("shows volume controls only when they do something", () => {
    const { rerender } = render(<BandMeters bar={bar(0)} />);
    expect(screen.queryByLabelText("Guitar volume")).toBeNull();

    rerender(<BandMeters bar={bar(0)} onVolume={vi.fn()} />);
    expect(screen.getByLabelText("Guitar volume")).toBeDefined();
  });

  it("reports volume changes for the right player", () => {
    const onVolume = vi.fn();
    render(<BandMeters bar={bar(0)} onVolume={onVolume} />);

    fireEvent.change(screen.getByLabelText("Keyboard volume"), { target: { value: "0.3" } });

    expect(onVolume).toHaveBeenCalledWith("keys", 0.3);
  });
});
