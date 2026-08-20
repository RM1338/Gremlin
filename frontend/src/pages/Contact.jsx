import { useState } from "react";
import { SiteNav, SiteFooter, DotField, FaqList } from "../lib/SiteChrome.jsx";
import { Check } from "../lib/icons.jsx";

/* No hero on this page. Someone who clicked Contact has already decided; a
 * full-height headline just puts the form below the fold. Form first, then the
 * questions that might have brought them here in the first place. */

const REASONS = ["Trying it on our app", "Self-hosted / air-gapped", "A framework we don't support yet", "Something else"];

export default function Contact() {
  const [sent, setSent] = useState(false);

  // No backend for this yet, so it says so rather than pretending to deliver.
  function submit(e) {
    e.preventDefault();
    setSent(true);
  }

  return (
    <div className="site">
      <SiteNav />

      <section className="contact-top">
        <DotField soft />
        <div className="contact-grid">
          <div className="contact-intro">
            <h1>Contact us</h1>
            <p>
              Gremlin is in beta and the roadmap is still shaped by what people ask for. A specific
              app and a specific frustration is the most useful thing you can send.
            </p>
            <div className="contact-aside">
              <h3>What we can help with</h3>
              <ul>
                <li>Getting a first run against your build</li>
                <li>Running entirely inside your own network</li>
                <li>A framework beyond Flutter and React Native</li>
                <li>Reading a trace that does not make sense</li>
              </ul>
              <h3>What we cannot yet</h3>
              <ul>
                <li>iOS &mdash; the platform layer is Android only today</li>
                <li>Published benchmark numbers &mdash; the harness exists, the runs do not</li>
              </ul>
            </div>
          </div>

          <form className="contact-form" onSubmit={submit}>
            {sent ? (
              <div className="sent">
                <Check />
                <h3>Not actually sent yet</h3>
                <p>
                  This form has no backend behind it during beta, so nothing left your browser.
                  Until one is wired up, mail is the honest route &mdash; and saying so beats a fake
                  success message.
                </p>
              </div>
            ) : (
              <>
                <label>Your name<input required placeholder="Your name" /></label>
                <label>Email address<input required type="email" placeholder="you@company.com" /></label>
                <label>
                  What brings you here
                  <select defaultValue={REASONS[0]}>
                    {REASONS.map((r) => <option key={r}>{r}</option>)}
                  </select>
                </label>
                <label>What would you point it at?<textarea rows={5} placeholder="The app, the framework, and the thing that keeps breaking." /></label>
                <button className="btn btn-primary btn-lg" type="submit">Send message</button>
              </>
            )}
          </form>
        </div>
      </section>

      <section className="section faq">
        <h2 className="section-title">Frequently asked questions</h2>
        <p className="section-lede">The ones that come up before anybody writes in.</p>
        <FaqList />
      </section>

      <SiteFooter />
    </div>
  );
}
