import { ENV } from "@/env";
import { NavData } from "@/types/navigation";
import { useMemo } from "react";
import { FaCompactDisc, FaVideo } from "react-icons/fa";
import { LuConstruction } from "react-icons/lu";
import { MdVideoLibrary } from "react-icons/md";

export default function useNavigation(
  variant: "primary" | "secondary" = "primary",
) {

  return useMemo(
    () =>
      [
        {
          id: 1,
          variant,
          icon: FaVideo,
          title: "Live",
          url: "/",
        },
        {
          id: 2,
          variant,
          icon: MdVideoLibrary,
          title: "Review",
          url: "/review",
        },
        {
          id: 3,
          variant,
          icon: FaCompactDisc,
          title: "Export",
          url: "/export",
        },
        {
          id: 4,
          variant,
          icon: LuConstruction,
          title: "UI Playground",
          url: "/playground",
          enabled: ENV !== "production",
        },
      ] as NavData[],
      [false, variant],
  );
}
