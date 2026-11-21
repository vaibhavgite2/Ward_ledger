"use client";
import { Suspense } from "react";
import LoginForm from "@/components/LoginForm";
import { Loading } from "@/components/Ui";

export default function ContractorLogin() {
  return (
    <Suspense fallback={<Loading />}>
      <LoginForm role="contractor" />
    </Suspense>
  );
}
