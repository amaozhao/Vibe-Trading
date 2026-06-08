import { render, screen } from "@testing-library/react";
import { MarkdownContent } from "../MarkdownContent";

vi.mock("react-markdown", () => ({
  default: ({ children }: { children: string }) => <div data-testid="markdown">{children}</div>,
}));
vi.mock("remark-gfm", () => ({ default: () => {} }));
vi.mock("rehype-highlight", () => ({ default: () => {} }));

describe("MarkdownContent", () => {
  it("renders content through the markdown renderer", () => {
    render(<MarkdownContent>| code | name |\n|---|---|\n| 300750 | 宁德时代 |</MarkdownContent>);

    expect(screen.getByTestId("markdown")).toHaveTextContent("300750");
    expect(screen.getByTestId("markdown")).toHaveTextContent("宁德时代");
  });
});
