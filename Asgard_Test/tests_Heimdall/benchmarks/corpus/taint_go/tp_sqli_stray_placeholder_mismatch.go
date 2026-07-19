// TP: WS4 Go SQL placeholder-count precision. The query literal has only
// ONE real `?` placeholder, but TWO trailing arguments are passed --
// `extra` doesn't correspond to any bind slot, so this call is NOT
// genuinely parameterized (placeholder_count < trailing_count). Rather
// than trusting the bare presence of a `?` character in the literal, the
// engine must fall through to scanning every argument and flag the
// tainted `extra` value -- a bare "does the literal contain a `?`"
// substring check would have wrongly classified this whole call as safe
// and silently muted the flow.
package main

import (
	"database/sql"
	"net/http"
)

func handler(w http.ResponseWriter, r *http.Request, db *sql.DB) {
	extra := r.URL.Query().Get("extra")
	rows, _ := db.Query("SELECT * FROM users WHERE name = ?", "bob", extra)
	_ = rows
}
