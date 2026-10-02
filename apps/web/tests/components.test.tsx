import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { Badge, Progress, Segmented } from "@/components/ui/misc";
import { Button } from "@/components/ui/button";

describe("ui primitives", () => {
  it("progress width reflects real value and clamps", () => {
    const { container, rerender } = render(<Progress value={0.42} />);
    expect((container.firstElementChild!.firstElementChild as HTMLElement).style.width).toBe("42%");
    rerender(<Progress value={3} />);
    expect((container.firstElementChild!.firstElementChild as HTMLElement).style.width).toBe("100%");
  });
  it("segmented control switches mode", () => {
    const fn = vi.fn();
    render(<Segmented value="fast" onChange={fn} options={[{ value: "fast", label: "Fast" }, { value: "quality", label: "Quality" }]} />);
    fireEvent.click(screen.getByText("Quality"));
    expect(fn).toHaveBeenCalledWith("quality");
  });
  it("disabled generate button does not fire", () => {
    const fn = vi.fn();
    render(<Button disabled onClick={fn}>Generate</Button>);
    fireEvent.click(screen.getByText("Generate"));
    expect(fn).not.toHaveBeenCalled();
  });
  it("badge renders", () => {
    render(<Badge tone="ok">QC passed</Badge>);
    expect(screen.getByText("QC passed")).toBeTruthy();
  });
});
