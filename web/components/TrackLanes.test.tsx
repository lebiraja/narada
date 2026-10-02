import { render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { INSTRUMENTS } from "@/lib/audio/types";
import { PLAYER } from "@/lib/palette";

import { TrackLanes } from "./TrackLanes";

describe("TrackLanes", () => {
  beforeAll(() => {
    vi.stubGlobal("matchMedia", () => ({ matches: true }));
  });

  it("renders a lane for every player in the band", () => {
    render(<TrackLanes />);

    for (const instrument of INSTRUMENTS) {
      expect(screen.getByText(PLAYER[instrument].name)).toBeTruthy();
    }
  });
});
