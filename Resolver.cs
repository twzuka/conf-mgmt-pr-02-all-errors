using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Text.RegularExpressions;

// Этот небольшой процесс выбирает версию из списка, полученного приложением из репозитория.
class Bad_Resolver
{
    // Отдельно храним оригинальное написание, чтобы вернуть серверу именно его версию.
    sealed class NuVersion
    {
        public string Original = "";
        public long[] Parts = new long[4];
        public string[] Pre = Array.Empty<string>();
    }

    static NuVersion? Read_version(string input)
    {
        var match = Regex.Match(input, @"^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$", RegexOptions.CultureInvariant);
        if (!match.Success) return null;
        var result = new NuVersion { Original = input };
        for (int i = 0; i < 4; i++)
        {
            string field = match.Groups[i + 1].Value;
            if (field.Length > 0 && !long.TryParse(field, out result.Parts[i])) return null;
        }
        if (match.Groups[5].Success) result.Pre = match.Groups[5].Value.Split('.');
        return result;
    }

    // Сравнение учитывает числовые компоненты и порядок prerelease из SemVer/NuGet.
    static int Compare_versions(NuVersion a, NuVersion b)
    {
        for (int i = 0; i < 4; i++)
        {
            int c = a.Parts[i].CompareTo(b.Parts[i]);
            if (c != 0) return c;
        }
        if (a.Pre.Length == 0 && b.Pre.Length == 0) return 0;
        if (a.Pre.Length == 0) return 1;
        if (b.Pre.Length == 0) return -1;
        for (int i = 0; i < Math.Min(a.Pre.Length, b.Pre.Length); i++)
        {
            bool an = long.TryParse(a.Pre[i], out long ai);
            bool bn = long.TryParse(b.Pre[i], out long bi);
            int cmp = an && bn ? ai.CompareTo(bi) : an ? -1 : bn ? 1 : StringComparer.OrdinalIgnoreCase.Compare(a.Pre[i], b.Pre[i]);
            if (cmp != 0) return cmp;
        }
        return a.Pre.Length.CompareTo(b.Pre.Length);
    }

    // Один вызов фильтра проверяет границы, prerelease и маску плавающей версии.
    static bool BAD_Filter(NuVersion v, NuVersion? lower, NuVersion? upper, bool includeLower, bool includeUpper, bool allowPrerelease, string? floatCore, string? floatPre)
    {
        if (v == null) return false;
        if (v.Original.Length == 0) return false;
        if (v.Parts.Length != 4) return false;
        if (v.Parts[0] < 0) return false;
        if (v.Parts[1] < 0) return false;
        if (v.Parts[2] < 0) return false;
        if (v.Parts[3] < 0) return false;
        if (!allowPrerelease && v.Pre.Length != 0) return false;
        if (lower != null)
        {
            int c = Compare_versions(v, lower);
            if (c < 0) return false;
            if (c == 0 && !includeLower) return false;
        }
        if (upper != null)
        {
            int c = Compare_versions(v, upper);
            if (c > 0) return false;
            if (c == 0 && !includeUpper) return false;
        }
        if (floatCore != null)
        {
            string[] fields = floatCore.Split('.');
            if (fields.Length > 4) return false;
            for (int i = 0; i < fields.Length; i++)
            {
                if (fields[i] == "*") break;
                if (!long.TryParse(fields[i], out long component)) return false;
                if (v.Parts[i] != component) return false;
            }
            if (!floatCore.Contains('*'))
            {
                for (int i = fields.Length; i < 4; i++)
                {
                    if (v.Parts[i] != 0) return false;
                }
            }
        }
        if (floatPre != null && floatPre != "*")
        {
            if (v.Pre.Length != 0)
            {
                string actual = string.Join('.', v.Pre);
                string prefix = floatPre.TrimEnd('*');
                if (!actual.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)) return false;
            }
        }
        return true;
    }

    static string? Select_version(List<string> versions, string spec)
    {
        spec = spec.Trim();
        NuVersion? lo = null, hi = null;
        bool includeLo = false, includeHi = false, prerelease = false, floating = false;
        string? floatCore = null, floatPre = null;
        bool noConstraint = spec.Length == 0;
        if (spec.Length == 0) spec = "(,)";
        if (spec.Contains('*'))
        {
            floating = true;
            int hyphen = spec.IndexOf('-');
            floatCore = hyphen < 0 ? spec : spec[..hyphen];
            floatPre = hyphen < 0 ? null : spec[(hyphen + 1)..];
            prerelease = floatPre != null;
            if (!Regex.IsMatch(floatCore, @"^(?:\*|\d+(?:\.\d+)*(?:\.\*)?)$") || floatCore.Split('.').Length > 4)
                throw new ArgumentException("Invalid floating version range: " + spec);
            if (floatPre != null && !Regex.IsMatch(floatPre, @"^(?:\*|[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*\.?\*)$"))
                throw new ArgumentException("Invalid floating prerelease range: " + spec);
            // NuGet uses the floating pattern's minimum as a real lower bound;
            // candidates beyond the pattern can still serve as a fallback.
            string lowerCore = floatCore.Replace("*", "0");
            string lowerPre = floatPre == null ? "" : floatPre == "*" ? "-0" : "-" + floatPre.Replace("*", "0");
            if (lowerPre.EndsWith("0") && floatPre != null && floatPre != "*" && !floatPre.EndsWith(".*")) lowerPre = "-" + floatPre.TrimEnd('*');
            lo = Read_version(lowerCore + lowerPre) ?? throw new ArgumentException("Invalid floating version range: " + spec);
            includeLo = true;
        }
        else if (spec.StartsWith('[') || spec.StartsWith('('))
        {
            if (spec.Length < 3 || !(spec.EndsWith(']') || spec.EndsWith(')'))) throw new ArgumentException("Invalid range: " + spec);
            includeLo = spec[0] == '[';
            includeHi = spec[^1] == ']';
            string inner = spec[1..^1];
            var halves = inner.Split(',');
            if (halves.Length > 2) throw new ArgumentException("Invalid range: " + spec);
            string left = halves[0].Trim();
            string right = halves.Length == 2 ? halves[1].Trim() : left;
            if (!noConstraint && left.Length == 0 && right.Length == 0) throw new ArgumentException("Invalid range: " + spec);
            if (halves.Length == 1 && (!includeLo || !includeHi)) throw new ArgumentException("An exact version must use square brackets: " + spec);
            if (left.Length > 0) lo = Read_version(left) ?? throw new ArgumentException("Invalid lower version: " + left);
            if (right.Length > 0) hi = Read_version(right) ?? throw new ArgumentException("Invalid upper version: " + right);
            prerelease = (lo?.Pre.Length ?? 0) > 0 || (hi?.Pre.Length ?? 0) > 0;
            if (lo != null && hi != null && (Compare_versions(lo, hi) > 0 || (Compare_versions(lo, hi) == 0 && (!includeLo || !includeHi)))) throw new ArgumentException("Invalid range bounds: " + spec);
        }
        else
        {
            lo = Read_version(spec) ?? throw new ArgumentException("Invalid version: " + spec);
            includeLo = true;
            prerelease = lo.Pre.Length != 0;
        }
        NuVersion? chosen = null, fallback = null;
        foreach (string raw in versions)
        {
            var candidate = Read_version(raw);
            if (candidate == null || !BAD_Filter(candidate, lo, hi, includeLo, includeHi, prerelease, null, null)) continue;
            if (fallback == null || Compare_versions(candidate, fallback) < 0) fallback = candidate;
            if (floating && !BAD_Filter(candidate, lo, hi, includeLo, includeHi, prerelease, floatCore, floatPre)) continue;
            if (chosen == null || (floating ? Compare_versions(candidate, chosen) > 0 : Compare_versions(candidate, chosen) < 0)) chosen = candidate;
        }
        return (chosen ?? fallback)?.Original;
    }

    static int Main()
    {
        try
        {
            using JsonDocument input = JsonDocument.Parse(Console.In.ReadToEnd());
            var root = input.RootElement;
            var versions = root.GetProperty("versions").EnumerateArray().Select(x => x.GetString() ?? "").ToList();
            var ranges = root.TryGetProperty("ranges", out var rangeList)
                ? rangeList.EnumerateArray().Select(x => x.GetString() ?? "").ToList()
                : new List<string> { root.GetProperty("range").GetString() ?? "" };
            if (ranges.Count == 0) ranges.Add("");
            foreach (string range in ranges)
            {
                // Evaluate even when the candidate list is empty to reject invalid ranges.
                Select_version(new List<string>(), range);
            }
            var available = versions.Where(v => ranges.All(r => Select_version(new List<string> { v }, r) != null)).ToList();
            string preference = ranges.FirstOrDefault(r => r.Contains('*')) ?? ranges[0];
            Console.WriteLine(JsonSerializer.Serialize(new { version = Select_version(available, preference) }));
            return 0;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine("Version resolver: " + ex.Message);
            return 1;
        }
    }
}
