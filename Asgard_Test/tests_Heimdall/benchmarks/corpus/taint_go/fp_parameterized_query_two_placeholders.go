// FP sibling of tp_sqli_stray_placeholder_mismatch.go: here the literal has
// TWO `?` placeholders and exactly TWO trailing args -- a genuinely
// parameterized query (placeholder_count == trailing_count) -- must stay
// clean, proving the placeholder-count check isn't simply "any `?`
// present" but actually verifies the counts line up.
package main

import (
	"database/sql"
	"net/http"
)

func handler(w http.ResponseWriter, r *http.Request, db *sql.DB) {
	name := r.URL.Query().Get("name")
	role := r.URL.Query().Get("role")
	rows, _ := db.Query("SELECT * FROM users WHERE name = ? AND role = ?", name, role)
	_ = rows
}
