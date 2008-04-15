import org.python.core.*;

public class random extends java.lang.Object {
    static String[] jpy$mainProperties = new String[] {"python.modules.builtin", "exceptions:org.python.core.exceptions"};
    static String[] jpy$proxyProperties = new String[] {"python.modules.builtin", "exceptions:org.python.core.exceptions", "python.options.showJavaExceptions", "true"};
    static String[] jpy$packages = new String[] {"java.net", null, "java.lang", null, "org.python.core", null, "java.io", null, "java.util.zip", null};
    
    public static class _PyInner extends PyFunctionTable implements PyRunnable {
        private static PyObject s$0;
        private static PyObject s$1;
        private static PyObject s$2;
        private static PyObject s$3;
        private static PyObject s$4;
        private static PyObject s$5;
        private static PyObject s$6;
        private static PyObject s$7;
        private static PyObject s$8;
        private static PyObject s$9;
        private static PyObject s$10;
        private static PyObject s$11;
        private static PyObject s$12;
        private static PyObject s$13;
        private static PyObject s$14;
        private static PyObject s$15;
        private static PyObject s$16;
        private static PyObject s$17;
        private static PyObject s$18;
        private static PyObject s$19;
        private static PyObject s$20;
        private static PyObject s$21;
        private static PyObject s$22;
        private static PyObject s$23;
        private static PyObject f$24;
        private static PyObject s$25;
        private static PyObject i$26;
        private static PyObject f$27;
        private static PyObject f$28;
        private static PyObject s$29;
        private static PyObject f$30;
        private static PyObject s$31;
        private static PyObject f$32;
        private static PyObject f$33;
        private static PyObject s$34;
        private static PyObject f$35;
        private static PyObject f$36;
        private static PyObject f$37;
        private static PyObject s$38;
        private static PyObject f$39;
        private static PyObject i$40;
        private static PyObject s$41;
        private static PyObject s$42;
        private static PyObject i$43;
        private static PyObject i$44;
        private static PyObject l$45;
        private static PyObject i$46;
        private static PyObject i$47;
        private static PyObject i$48;
        private static PyObject s$49;
        private static PyObject i$50;
        private static PyObject i$51;
        private static PyObject i$52;
        private static PyObject i$53;
        private static PyObject i$54;
        private static PyObject i$55;
        private static PyObject f$56;
        private static PyObject f$57;
        private static PyObject f$58;
        private static PyObject s$59;
        private static PyObject s$60;
        private static PyObject i$61;
        private static PyObject s$62;
        private static PyObject s$63;
        private static PyObject s$64;
        private static PyObject s$65;
        private static PyObject s$66;
        private static PyObject s$67;
        private static PyObject i$68;
        private static PyObject i$69;
        private static PyObject s$70;
        private static PyObject s$71;
        private static PyObject s$72;
        private static PyObject s$73;
        private static PyObject s$74;
        private static PyObject s$75;
        private static PyObject s$76;
        private static PyObject s$77;
        private static PyObject s$78;
        private static PyObject s$79;
        private static PyObject s$80;
        private static PyObject f$81;
        private static PyObject f$82;
        private static PyObject s$83;
        private static PyObject s$84;
        private static PyObject s$85;
        private static PyObject f$86;
        private static PyObject s$87;
        private static PyObject s$88;
        private static PyObject s$89;
        private static PyObject s$90;
        private static PyObject s$91;
        private static PyObject s$92;
        private static PyObject s$93;
        private static PyObject s$94;
        private static PyObject s$95;
        private static PyObject s$96;
        private static PyObject s$97;
        private static PyObject s$98;
        private static PyObject s$99;
        private static PyObject s$100;
        private static PyObject s$101;
        private static PyObject s$102;
        private static PyObject s$103;
        private static PyObject s$104;
        private static PyObject s$105;
        private static PyObject s$106;
        private static PyObject s$107;
        private static PyObject s$108;
        private static PyObject s$109;
        private static PyObject i$110;
        private static PyObject s$111;
        private static PyObject s$112;
        private static PyFunctionTable funcTable;
        private static PyCode c$0__verify;
        private static PyCode c$1___init__;
        private static PyCode c$2_seed;
        private static PyCode c$3_random;
        private static PyCode c$4_getstate;
        private static PyCode c$5_setstate;
        private static PyCode c$6_jumpahead;
        private static PyCode c$7__Random__whseed;
        private static PyCode c$8_whseed;
        private static PyCode c$9___getstate__;
        private static PyCode c$10___setstate__;
        private static PyCode c$11_randrange;
        private static PyCode c$12_randint;
        private static PyCode c$13_choice;
        private static PyCode c$14_shuffle;
        private static PyCode c$15_uniform;
        private static PyCode c$16_normalvariate;
        private static PyCode c$17_lognormvariate;
        private static PyCode c$18_cunifvariate;
        private static PyCode c$19_expovariate;
        private static PyCode c$20_vonmisesvariate;
        private static PyCode c$21_gammavariate;
        private static PyCode c$22_stdgamma;
        private static PyCode c$23_gauss;
        private static PyCode c$24_betavariate;
        private static PyCode c$25_paretovariate;
        private static PyCode c$26_weibullvariate;
        private static PyCode c$27_Random;
        private static PyCode c$28__test_generator;
        private static PyCode c$29__test;
        private static PyCode c$30_main;
        private static void initConstants() {
            s$0 = Py.newString("Random variable generators.\012\012    integers\012    --------\012           uniform within range\012\012    sequences\012    ---------\012           pick random element\012           generate random permutation\012\012    distributions on the real line:\012    ------------------------------\012           uniform\012           normal (Gaussian)\012           lognormal\012           negative exponential\012           gamma\012           beta\012\012    distributions on the circle (angles 0 to 2pi)\012    ---------------------------------------------\012           circular uniform\012           von Mises\012\012Translated from anonymously contributed C/C++ source.\012\012Multi-threading note:  the random number generator used here is not thread-\012safe; it is possible that two calls return the same random value.  However,\012you can instantiate a different instance of Random() in each thread to get\012generators that don't share state, then use .setstate() and .jumpahead() to\012move the generators to disjoint segments of the full period.  For example,\012\012def create_generators(num, delta, firstseed=None):\012    \"\"\"Return list of num distinct generators.\012    Each generator has its own unique segment of delta elements from\012    Random.random()'s full period.\012    Seed the first generator with optional arg firstseed (default is\012    None, to seed from current time).\012    \"\"\"\012\012    from random import Random\012    g = Random(firstseed)\012    result = [g]\012    for i in range(num - 1):\012        laststate = g.getstate()\012        g = Random()\012        g.setstate(laststate)\012        g.jumpahead(delta)\012        result.append(g)\012    return result\012\012gens = create_generators(10, 1000000)\012\012That creates 10 distinct generators, which can be passed out to 10 distinct\012threads.  The generators don't share state so can be called safely in\012parallel.  So long as no thread calls its g.random() more than a million\012times (the second argument to create_generators), the sequences seen by\012each thread will not overlap.\012\012The period of the underlying Wichmann-Hill generator is 6,953,607,871,644,\012and that limits how far this technique can be pushed.\012\012Just for fun, note that since we know the period, .jumpahead() can also be\012used to \"move backward in time\":\012\012>>> g = Random(42)  # arbitrary\012>>> g.random()\0120.25420336316883324\012>>> g.jumpahead(6953607871644L - 1) # move *back* one\012>>> g.random()\0120.25420336316883324\012");
            s$1 = Py.newString("Random");
            s$2 = Py.newString("seed");
            s$3 = Py.newString("random");
            s$4 = Py.newString("uniform");
            s$5 = Py.newString("randint");
            s$6 = Py.newString("choice");
            s$7 = Py.newString("randrange");
            s$8 = Py.newString("shuffle");
            s$9 = Py.newString("normalvariate");
            s$10 = Py.newString("lognormvariate");
            s$11 = Py.newString("cunifvariate");
            s$12 = Py.newString("expovariate");
            s$13 = Py.newString("vonmisesvariate");
            s$14 = Py.newString("gammavariate");
            s$15 = Py.newString("stdgamma");
            s$16 = Py.newString("gauss");
            s$17 = Py.newString("betavariate");
            s$18 = Py.newString("paretovariate");
            s$19 = Py.newString("weibullvariate");
            s$20 = Py.newString("getstate");
            s$21 = Py.newString("setstate");
            s$22 = Py.newString("jumpahead");
            s$23 = Py.newString("whseed");
            f$24 = Py.newFloat(1.0E-7);
            s$25 = Py.newString("computed value for %s deviates too much (computed %g, expected %g)");
            i$26 = Py.newInteger(4);
            f$27 = Py.newFloat(0.5);
            f$28 = Py.newFloat(2.0);
            s$29 = Py.newString("NV_MAGICCONST");
            f$30 = Py.newFloat(1.71552776992141);
            s$31 = Py.newString("TWOPI");
            f$32 = Py.newFloat(6.28318530718);
            f$33 = Py.newFloat(4.0);
            s$34 = Py.newString("LOG4");
            f$35 = Py.newFloat(1.38629436111989);
            f$36 = Py.newFloat(1.0);
            f$37 = Py.newFloat(4.5);
            s$38 = Py.newString("SG_MAGICCONST");
            f$39 = Py.newFloat(2.50407739677627);
            i$40 = Py.newInteger(1);
            s$41 = Py.newString("Initialize an instance.\012\012        Optional argument x controls seeding, as for Random.seed().\012        ");
            s$42 = Py.newString("Initialize internal state from hashable object.\012\012        None or no argument seeds from current time.\012\012        If a is not None or an int or long, hash(a) is used instead.\012\012        If a is an int or long, a is used directly.  Distinct values between\012        0 and 27814431486575L inclusive are guaranteed to yield distinct\012        internal states (this guarantee is specific to the default\012        Wichmann-Hill generator).\012        ");
            i$43 = Py.newInteger(256);
            i$44 = Py.newInteger(3);
            l$45 = Py.newLong("3");
            i$46 = Py.newInteger(30268);
            i$47 = Py.newInteger(30306);
            i$48 = Py.newInteger(30322);
            s$49 = Py.newString("Get the next random number in the range [0.0, 1.0).");
            i$50 = Py.newInteger(171);
            i$51 = Py.newInteger(30269);
            i$52 = Py.newInteger(172);
            i$53 = Py.newInteger(30307);
            i$54 = Py.newInteger(170);
            i$55 = Py.newInteger(30323);
            f$56 = Py.newFloat(30269.0);
            f$57 = Py.newFloat(30307.0);
            f$58 = Py.newFloat(30323.0);
            s$59 = Py.newString("Return internal state; can be passed to setstate() later.");
            s$60 = Py.newString("Restore internal state from object returned by getstate().");
            i$61 = Py.newInteger(0);
            s$62 = Py.newString("state with version %s passed to Random.setstate() of version %s");
            s$63 = Py.newString("Act as if n calls to random() were made, but quickly.\012\012        n is an int, greater than or equal to 0.\012\012        Example use:  If you have 2 threads and know that each will\012        consume no more than a million random numbers, create two Random\012        objects r1 and r2, then do\012            r2.setstate(r1.getstate())\012            r2.jumpahead(1000000)\012        Then r1 and r2 will use guaranteed-disjoint segments of the full\012        period.\012        ");
            s$64 = Py.newString("n must be >= 0");
            s$65 = Py.newString("Set the Wichmann-Hill seed from (x, y, z).\012\012        These must be integers in the range [0, 256).\012        ");
            s$66 = Py.newString("seeds must be integers");
            s$67 = Py.newString("seeds must be in range(0, 256)");
            i$68 = Py.newInteger(16777215);
            i$69 = Py.newInteger(24);
            s$70 = Py.newString("Seed from hashable object's hash code.\012\012        None or no argument seeds from current time.  It is not guaranteed\012        that objects with distinct hash codes lead to distinct internal\012        states.\012\012        This is obsolete, provided for compatibility with the seed routine\012        used prior to Python 2.1.  Use the .seed() method instead.\012        ");
            s$71 = Py.newString("Choose a random item from range(start, stop[, step]).\012\012        This fixes the problem with randint() which includes the\012        endpoint; in Python this is usually not what you want.\012        Do not supply the 'int' and 'default' arguments.\012        ");
            s$72 = Py.newString("non-integer arg 1 for randrange()");
            s$73 = Py.newString("empty range for randrange()");
            s$74 = Py.newString("non-integer stop for randrange()");
            s$75 = Py.newString("non-integer step for randrange()");
            s$76 = Py.newString("zero step for randrange()");
            s$77 = Py.newString("Return random integer in range [a, b], including both end points.\012\012        (Deprecated; use randrange(a, b+1).)\012        ");
            s$78 = Py.newString("Choose a random element from a non-empty sequence.");
            s$79 = Py.newString("x, random=random.random -> shuffle list x in place; return None.\012\012        Optional arg random is a 0-argument function returning a random\012        float in [0.0, 1.0); by default, the standard random.random.\012\012        Note that for even rather small len(x), the total number of\012        permutations of x is larger than the period of most random number\012        generators; this implies that \"most\" permutations of a long\012        sequence can never be generated.\012        ");
            s$80 = Py.newString("Get a random number in the range [a, b).");
            f$81 = Py.newFloat(1.0E-6);
            f$82 = Py.newFloat(0.0);
            s$83 = Py.newString("stdgamma: alpha must be > 0.0");
            s$84 = Py.newString("times");
            s$85 = Py.newString("eval");
            f$86 = Py.newFloat(1.0E10);
            s$87 = Py.newString("sec,");
            s$88 = Py.newString("avg %g, stddev %g, min %g, max %g");
            s$89 = Py.newString("TWOPI         =");
            s$90 = Py.newString("LOG4          =");
            s$91 = Py.newString("NV_MAGICCONST =");
            s$92 = Py.newString("SG_MAGICCONST =");
            s$93 = Py.newString("random()");
            s$94 = Py.newString("normalvariate(0.0, 1.0)");
            s$95 = Py.newString("lognormvariate(0.0, 1.0)");
            s$96 = Py.newString("cunifvariate(0.0, 1.0)");
            s$97 = Py.newString("expovariate(1.0)");
            s$98 = Py.newString("vonmisesvariate(0.0, 1.0)");
            s$99 = Py.newString("gammavariate(0.5, 1.0)");
            s$100 = Py.newString("gammavariate(0.9, 1.0)");
            s$101 = Py.newString("gammavariate(1.0, 1.0)");
            s$102 = Py.newString("gammavariate(2.0, 1.0)");
            s$103 = Py.newString("gammavariate(20.0, 1.0)");
            s$104 = Py.newString("gammavariate(200.0, 1.0)");
            s$105 = Py.newString("gauss(0.0, 1.0)");
            s$106 = Py.newString("betavariate(3.0, 3.0)");
            s$107 = Py.newString("paretovariate(1.0)");
            s$108 = Py.newString("weibullvariate(1.0, 1.0)");
            s$109 = Py.newString("jumpahead test failed ");
            i$110 = Py.newInteger(200);
            s$111 = Py.newString("__main__");
            s$112 = Py.newString("/usr/share/jython/Lib/random.py");
            funcTable = new _PyInner();
            c$0__verify = Py.newCode(3, new String[] {"name", "computed", "expected"}, "/usr/share/jython/Lib/random.py", "_verify", false, false, funcTable, 0, null, null, 0, 1);
            c$1___init__ = Py.newCode(2, new String[] {"self", "x"}, "/usr/share/jython/Lib/random.py", "__init__", false, false, funcTable, 1, null, null, 0, 1);
            c$2_seed = Py.newCode(2, new String[] {"self", "a", "time", "z", "y", "x"}, "/usr/share/jython/Lib/random.py", "seed", false, false, funcTable, 2, null, null, 0, 1);
            c$3_random = Py.newCode(1, new String[] {"self", "x", "z", "y"}, "/usr/share/jython/Lib/random.py", "random", false, false, funcTable, 3, null, null, 0, 1);
            c$4_getstate = Py.newCode(1, new String[] {"self"}, "/usr/share/jython/Lib/random.py", "getstate", false, false, funcTable, 4, null, null, 0, 1);
            c$5_setstate = Py.newCode(2, new String[] {"self", "state", "version"}, "/usr/share/jython/Lib/random.py", "setstate", false, false, funcTable, 5, null, null, 0, 1);
            c$6_jumpahead = Py.newCode(2, new String[] {"self", "n", "x", "z", "y"}, "/usr/share/jython/Lib/random.py", "jumpahead", false, false, funcTable, 6, null, null, 0, 1);
            c$7__Random__whseed = Py.newCode(4, new String[] {"self", "x", "y", "z", "time", "t"}, "/usr/share/jython/Lib/random.py", "_Random__whseed", false, false, funcTable, 7, null, null, 0, 1);
            c$8_whseed = Py.newCode(2, new String[] {"self", "a", "x", "z", "y"}, "/usr/share/jython/Lib/random.py", "whseed", false, false, funcTable, 8, null, null, 0, 1);
            c$9___getstate__ = Py.newCode(1, new String[] {"self"}, "/usr/share/jython/Lib/random.py", "__getstate__", false, false, funcTable, 9, null, null, 0, 1);
            c$10___setstate__ = Py.newCode(2, new String[] {"self", "state"}, "/usr/share/jython/Lib/random.py", "__setstate__", false, false, funcTable, 10, null, null, 0, 1);
            c$11_randrange = Py.newCode(6, new String[] {"self", "start", "stop", "step", "int", "default", "istep", "n", "istart", "istop"}, "/usr/share/jython/Lib/random.py", "randrange", false, false, funcTable, 11, null, null, 0, 1);
            c$12_randint = Py.newCode(3, new String[] {"self", "a", "b"}, "/usr/share/jython/Lib/random.py", "randint", false, false, funcTable, 12, null, null, 0, 1);
            c$13_choice = Py.newCode(2, new String[] {"self", "seq"}, "/usr/share/jython/Lib/random.py", "choice", false, false, funcTable, 13, null, null, 0, 1);
            c$14_shuffle = Py.newCode(4, new String[] {"self", "x", "random", "int", "j", "i"}, "/usr/share/jython/Lib/random.py", "shuffle", false, false, funcTable, 14, null, null, 0, 1);
            c$15_uniform = Py.newCode(3, new String[] {"self", "a", "b"}, "/usr/share/jython/Lib/random.py", "uniform", false, false, funcTable, 15, null, null, 0, 1);
            c$16_normalvariate = Py.newCode(3, new String[] {"self", "mu", "sigma", "u2", "u1", "random", "zz", "z"}, "/usr/share/jython/Lib/random.py", "normalvariate", false, false, funcTable, 16, null, null, 0, 1);
            c$17_lognormvariate = Py.newCode(3, new String[] {"self", "mu", "sigma"}, "/usr/share/jython/Lib/random.py", "lognormvariate", false, false, funcTable, 17, null, null, 0, 1);
            c$18_cunifvariate = Py.newCode(3, new String[] {"self", "mean", "arc"}, "/usr/share/jython/Lib/random.py", "cunifvariate", false, false, funcTable, 18, null, null, 0, 1);
            c$19_expovariate = Py.newCode(2, new String[] {"self", "lambd", "u", "random"}, "/usr/share/jython/Lib/random.py", "expovariate", false, false, funcTable, 19, null, null, 0, 1);
            c$20_vonmisesvariate = Py.newCode(3, new String[] {"self", "mu", "kappa", "random", "theta", "z", "r", "u3", "u2", "u1", "f", "c", "b", "a"}, "/usr/share/jython/Lib/random.py", "vonmisesvariate", false, false, funcTable, 20, null, null, 0, 1);
            c$21_gammavariate = Py.newCode(3, new String[] {"self", "alpha", "beta", "ainv"}, "/usr/share/jython/Lib/random.py", "gammavariate", false, false, funcTable, 21, null, null, 0, 1);
            c$22_stdgamma = Py.newCode(5, new String[] {"self", "alpha", "ainv", "bbb", "ccc", "random", "z", "x", "v", "u", "r", "p", "u2", "u1", "b"}, "/usr/share/jython/Lib/random.py", "stdgamma", false, false, funcTable, 22, null, null, 0, 1);
            c$23_gauss = Py.newCode(3, new String[] {"self", "mu", "sigma", "x2pi", "random", "g2rad", "z"}, "/usr/share/jython/Lib/random.py", "gauss", false, false, funcTable, 23, null, null, 0, 1);
            c$24_betavariate = Py.newCode(3, new String[] {"self", "alpha", "beta", "y"}, "/usr/share/jython/Lib/random.py", "betavariate", false, false, funcTable, 24, null, null, 0, 1);
            c$25_paretovariate = Py.newCode(2, new String[] {"self", "alpha", "u"}, "/usr/share/jython/Lib/random.py", "paretovariate", false, false, funcTable, 25, null, null, 0, 1);
            c$26_weibullvariate = Py.newCode(3, new String[] {"self", "alpha", "beta", "u"}, "/usr/share/jython/Lib/random.py", "weibullvariate", false, false, funcTable, 26, null, null, 0, 1);
            c$27_Random = Py.newCode(0, new String[] {}, "/usr/share/jython/Lib/random.py", "Random", false, false, funcTable, 27, null, null, 0, 0);
            c$28__test_generator = Py.newCode(2, new String[] {"n", "funccall", "smallest", "code", "sum", "largest", "time", "x", "t1", "t0", "avg", "i", "stddev", "sqsum"}, "/usr/share/jython/Lib/random.py", "_test_generator", false, false, funcTable, 28, null, null, 0, 1);
            c$29__test = Py.newCode(1, new String[] {"N", "r2", "r1", "i", "s"}, "/usr/share/jython/Lib/random.py", "_test", false, false, funcTable, 29, null, null, 0, 1);
            c$30_main = Py.newCode(0, new String[] {}, "/usr/share/jython/Lib/random.py", "main", false, false, funcTable, 30, null, null, 0, 0);
        }
        
        
        public PyCode getMain() {
            if (c$30_main == null) _PyInner.initConstants();
            return c$30_main;
        }
        
        public PyObject call_function(int index, PyFrame frame) {
            switch (index){
                case 0:
                return _PyInner._verify$1(frame);
                case 1:
                return _PyInner.__init__$2(frame);
                case 2:
                return _PyInner.seed$3(frame);
                case 3:
                return _PyInner.random$4(frame);
                case 4:
                return _PyInner.getstate$5(frame);
                case 5:
                return _PyInner.setstate$6(frame);
                case 6:
                return _PyInner.jumpahead$7(frame);
                case 7:
                return _PyInner._Random__whseed$8(frame);
                case 8:
                return _PyInner.whseed$9(frame);
                case 9:
                return _PyInner.__getstate__$10(frame);
                case 10:
                return _PyInner.__setstate__$11(frame);
                case 11:
                return _PyInner.randrange$12(frame);
                case 12:
                return _PyInner.randint$13(frame);
                case 13:
                return _PyInner.choice$14(frame);
                case 14:
                return _PyInner.shuffle$15(frame);
                case 15:
                return _PyInner.uniform$16(frame);
                case 16:
                return _PyInner.normalvariate$17(frame);
                case 17:
                return _PyInner.lognormvariate$18(frame);
                case 18:
                return _PyInner.cunifvariate$19(frame);
                case 19:
                return _PyInner.expovariate$20(frame);
                case 20:
                return _PyInner.vonmisesvariate$21(frame);
                case 21:
                return _PyInner.gammavariate$22(frame);
                case 22:
                return _PyInner.stdgamma$23(frame);
                case 23:
                return _PyInner.gauss$24(frame);
                case 24:
                return _PyInner.betavariate$25(frame);
                case 25:
                return _PyInner.paretovariate$26(frame);
                case 26:
                return _PyInner.weibullvariate$27(frame);
                case 27:
                return _PyInner.Random$28(frame);
                case 28:
                return _PyInner._test_generator$29(frame);
                case 29:
                return _PyInner._test$30(frame);
                case 30:
                return _PyInner.main$31(frame);
                default:
                return null;
            }
        }
        
        private static PyObject _verify$1(PyFrame frame) {
            if (frame.getglobal("abs").__call__(frame.getlocal(1)._sub(frame.getlocal(2)))._gt(f$24).__nonzero__()) {
                throw Py.makeException(frame.getglobal("ValueError").__call__(s$25._mod(new PyTuple(new PyObject[] {frame.getlocal(0), frame.getlocal(1), frame.getlocal(2)}))));
            }
            return Py.None;
        }
        
        private static PyObject __init__$2(PyFrame frame) {
            /* Initialize an instance.
            
                    Optional argument x controls seeding, as for Random.seed().
                     */
            frame.getlocal(0).invoke("seed", frame.getlocal(1));
            frame.getlocal(0).__setattr__("gauss_next", frame.getglobal("None"));
            return Py.None;
        }
        
        private static PyObject seed$3(PyFrame frame) {
            // Temporary Variables
            PyObject[] t$0$PyObject__;
            
            // Code
            /* Initialize internal state from hashable object.
            
                    None or no argument seeds from current time.
            
                    If a is not None or an int or long, hash(a) is used instead.
            
                    If a is an int or long, a is used directly.  Distinct values between
                    0 and 27814431486575L inclusive are guaranteed to yield distinct
                    internal states (this guarantee is specific to the default
                    Wichmann-Hill generator).
                     */
            if (frame.getlocal(1)._is(frame.getglobal("None")).__nonzero__()) {
                frame.setlocal(2, org.python.core.imp.importOne("time", frame));
                frame.setlocal(1, frame.getglobal("long").__call__(frame.getlocal(2).__getattr__("time").__call__()._mul(i$43)));
            }
            if (frame.getglobal("type").__call__(frame.getlocal(1))._notin(new PyTuple(new PyObject[] {frame.getglobal("type").__call__(i$44), frame.getglobal("type").__call__(l$45)})).__nonzero__()) {
                frame.setlocal(1, frame.getglobal("hash").__call__(frame.getlocal(1)));
            }
            t$0$PyObject__ = org.python.core.Py.unpackSequence(frame.getglobal("divmod").__call__(frame.getlocal(1), i$46), 2);
            frame.setlocal(1, t$0$PyObject__[0]);
            frame.setlocal(5, t$0$PyObject__[1]);
            t$0$PyObject__ = org.python.core.Py.unpackSequence(frame.getglobal("divmod").__call__(frame.getlocal(1), i$47), 2);
            frame.setlocal(1, t$0$PyObject__[0]);
            frame.setlocal(4, t$0$PyObject__[1]);
            t$0$PyObject__ = org.python.core.Py.unpackSequence(frame.getglobal("divmod").__call__(frame.getlocal(1), i$48), 2);
            frame.setlocal(1, t$0$PyObject__[0]);
            frame.setlocal(3, t$0$PyObject__[1]);
            frame.getlocal(0).__setattr__("_seed", new PyTuple(new PyObject[] {frame.getglobal("int").__call__(frame.getlocal(5))._add(i$40), frame.getglobal("int").__call__(frame.getlocal(4))._add(i$40), frame.getglobal("int").__call__(frame.getlocal(3))._add(i$40)}));
            return Py.None;
        }
        
        private static PyObject random$4(PyFrame frame) {
            // Temporary Variables
            PyObject[] t$0$PyObject__;
            
            // Code
            /* Get the next random number in the range [0.0, 1.0). */
            t$0$PyObject__ = org.python.core.Py.unpackSequence(frame.getlocal(0).__getattr__("_seed"), 3);
            frame.setlocal(1, t$0$PyObject__[0]);
            frame.setlocal(3, t$0$PyObject__[1]);
            frame.setlocal(2, t$0$PyObject__[2]);
            frame.setlocal(1, i$50._mul(frame.getlocal(1))._mod(i$51));
            frame.setlocal(3, i$52._mul(frame.getlocal(3))._mod(i$53));
            frame.setlocal(2, i$54._mul(frame.getlocal(2))._mod(i$55));
            frame.getlocal(0).__setattr__("_seed", new PyTuple(new PyObject[] {frame.getlocal(1), frame.getlocal(3), frame.getlocal(2)}));
            return frame.getlocal(1)._div(f$56)._add(frame.getlocal(3)._div(f$57))._add(frame.getlocal(2)._div(f$58))._mod(f$36);
        }
        
        private static PyObject getstate$5(PyFrame frame) {
            /* Return internal state; can be passed to setstate() later. */
            return new PyTuple(new PyObject[] {frame.getlocal(0).__getattr__("VERSION"), frame.getlocal(0).__getattr__("_seed"), frame.getlocal(0).__getattr__("gauss_next")});
        }
        
        private static PyObject setstate$6(PyFrame frame) {
            // Temporary Variables
            PyObject[] t$0$PyObject__;
            
            // Code
            /* Restore internal state from object returned by getstate(). */
            frame.setlocal(2, frame.getlocal(1).__getitem__(i$61));
            if (frame.getlocal(2)._eq(i$40).__nonzero__()) {
                t$0$PyObject__ = org.python.core.Py.unpackSequence(frame.getlocal(1), 3);
                frame.setlocal(2, t$0$PyObject__[0]);
                frame.getlocal(0).__setattr__("_seed", t$0$PyObject__[1]);
                frame.getlocal(0).__setattr__("gauss_next", t$0$PyObject__[2]);
            }
            else {
                throw Py.makeException(frame.getglobal("ValueError").__call__(s$62._mod(new PyTuple(new PyObject[] {frame.getlocal(2), frame.getlocal(0).__getattr__("VERSION")}))));
            }
            return Py.None;
        }
        
        private static PyObject jumpahead$7(PyFrame frame) {
            // Temporary Variables
            PyObject[] t$0$PyObject__;
            
            // Code
            /* Act as if n calls to random() were made, but quickly.
            
                    n is an int, greater than or equal to 0.
            
                    Example use:  If you have 2 threads and know that each will
                    consume no more than a million random numbers, create two Random
                    objects r1 and r2, then do
                        r2.setstate(r1.getstate())
                        r2.jumpahead(1000000)
                    Then r1 and r2 will use guaranteed-disjoint segments of the full
                    period.
                     */
            if (frame.getlocal(1)._ge(i$61).__not__().__nonzero__()) {
                throw Py.makeException(frame.getglobal("ValueError").__call__(s$64));
            }
            t$0$PyObject__ = org.python.core.Py.unpackSequence(frame.getlocal(0).__getattr__("_seed"), 3);
            frame.setlocal(2, t$0$PyObject__[0]);
            frame.setlocal(4, t$0$PyObject__[1]);
            frame.setlocal(3, t$0$PyObject__[2]);
            frame.setlocal(2, frame.getglobal("int").__call__(frame.getlocal(2)._mul(frame.getglobal("pow").__call__(i$50, frame.getlocal(1), i$51)))._mod(i$51));
            frame.setlocal(4, frame.getglobal("int").__call__(frame.getlocal(4)._mul(frame.getglobal("pow").__call__(i$52, frame.getlocal(1), i$53)))._mod(i$53));
            frame.setlocal(3, frame.getglobal("int").__call__(frame.getlocal(3)._mul(frame.getglobal("pow").__call__(i$54, frame.getlocal(1), i$55)))._mod(i$55));
            frame.getlocal(0).__setattr__("_seed", new PyTuple(new PyObject[] {frame.getlocal(2), frame.getlocal(4), frame.getlocal(3)}));
            return Py.None;
        }
        
        private static PyObject _Random__whseed$8(PyFrame frame) {
            // Temporary Variables
            PyObject[] t$0$PyObject__;
            PyObject t$0$PyObject, t$1$PyObject, t$2$PyObject;
            
            // Code
            /* Set the Wichmann-Hill seed from (x, y, z).
            
                    These must be integers in the range [0, 256).
                     */
            if ((frame.getglobal("type").__call__(frame.getlocal(1))._eq(t$0$PyObject = frame.getglobal("type").__call__(frame.getlocal(2))).__nonzero__() ? (t$0$PyObject._eq(t$1$PyObject = frame.getglobal("type").__call__(frame.getlocal(3))).__nonzero__() ? t$1$PyObject._eq(frame.getglobal("type").__call__(i$61)) : Py.Zero) : Py.Zero).__not__().__nonzero__()) {
                throw Py.makeException(frame.getglobal("TypeError").__call__(s$66));
            }
            if (((t$0$PyObject = ((t$1$PyObject = (i$61._le(t$2$PyObject = frame.getlocal(1)).__nonzero__() ? t$2$PyObject._lt(i$43) : Py.Zero)).__nonzero__() ? (i$61._le(t$2$PyObject = frame.getlocal(2)).__nonzero__() ? t$2$PyObject._lt(i$43) : Py.Zero) : t$1$PyObject)).__nonzero__() ? (i$61._le(t$1$PyObject = frame.getlocal(3)).__nonzero__() ? t$1$PyObject._lt(i$43) : Py.Zero) : t$0$PyObject).__not__().__nonzero__()) {
                throw Py.makeException(frame.getglobal("ValueError").__call__(s$67));
            }
            if ((i$61._eq(t$0$PyObject = frame.getlocal(1)).__nonzero__() ? (t$0$PyObject._eq(t$1$PyObject = frame.getlocal(2)).__nonzero__() ? t$1$PyObject._eq(frame.getlocal(3)) : Py.Zero) : Py.Zero).__nonzero__()) {
                frame.setlocal(4, org.python.core.imp.importOne("time", frame));
                frame.setlocal(5, frame.getglobal("long").__call__(frame.getlocal(4).__getattr__("time").__call__()._mul(i$43)));
                frame.setlocal(5, frame.getglobal("int").__call__(frame.getlocal(5)._and(i$68)._xor(frame.getlocal(5)._rshift(i$69))));
                t$0$PyObject__ = org.python.core.Py.unpackSequence(frame.getglobal("divmod").__call__(frame.getlocal(5), i$43), 2);
                frame.setlocal(5, t$0$PyObject__[0]);
                frame.setlocal(1, t$0$PyObject__[1]);
                t$0$PyObject__ = org.python.core.Py.unpackSequence(frame.getglobal("divmod").__call__(frame.getlocal(5), i$43), 2);
                frame.setlocal(5, t$0$PyObject__[0]);
                frame.setlocal(2, t$0$PyObject__[1]);
                t$0$PyObject__ = org.python.core.Py.unpackSequence(frame.getglobal("divmod").__call__(frame.getlocal(5), i$43), 2);
                frame.setlocal(5, t$0$PyObject__[0]);
                frame.setlocal(3, t$0$PyObject__[1]);
            }
            frame.getlocal(0).__setattr__("_seed", new PyTuple(new PyObject[] {(t$0$PyObject = frame.getlocal(1)).__nonzero__() ? t$0$PyObject : i$40, (t$0$PyObject = frame.getlocal(2)).__nonzero__() ? t$0$PyObject : i$40, (t$0$PyObject = frame.getlocal(3)).__nonzero__() ? t$0$PyObject : i$40}));
            return Py.None;
        }
        
        private static PyObject whseed$9(PyFrame frame) {
            // Temporary Variables
            PyObject[] t$0$PyObject__;
            PyObject t$0$PyObject;
            
            // Code
            /* Seed from hashable object's hash code.
            
                    None or no argument seeds from current time.  It is not guaranteed
                    that objects with distinct hash codes lead to distinct internal
                    states.
            
                    This is obsolete, provided for compatibility with the seed routine
                    used prior to Python 2.1.  Use the .seed() method instead.
                     */
            if (frame.getlocal(1)._is(frame.getglobal("None")).__nonzero__()) {
                frame.getlocal(0).invoke("_Random__whseed");
                return Py.None;
            }
            frame.setlocal(1, frame.getglobal("hash").__call__(frame.getlocal(1)));
            t$0$PyObject__ = org.python.core.Py.unpackSequence(frame.getglobal("divmod").__call__(frame.getlocal(1), i$43), 2);
            frame.setlocal(1, t$0$PyObject__[0]);
            frame.setlocal(2, t$0$PyObject__[1]);
            t$0$PyObject__ = org.python.core.Py.unpackSequence(frame.getglobal("divmod").__call__(frame.getlocal(1), i$43), 2);
            frame.setlocal(1, t$0$PyObject__[0]);
            frame.setlocal(4, t$0$PyObject__[1]);
            t$0$PyObject__ = org.python.core.Py.unpackSequence(frame.getglobal("divmod").__call__(frame.getlocal(1), i$43), 2);
            frame.setlocal(1, t$0$PyObject__[0]);
            frame.setlocal(3, t$0$PyObject__[1]);
            frame.setlocal(2, (t$0$PyObject = frame.getlocal(2)._add(frame.getlocal(1))._mod(i$43)).__nonzero__() ? t$0$PyObject : i$40);
            frame.setlocal(4, (t$0$PyObject = frame.getlocal(4)._add(frame.getlocal(1))._mod(i$43)).__nonzero__() ? t$0$PyObject : i$40);
            frame.setlocal(3, (t$0$PyObject = frame.getlocal(3)._add(frame.getlocal(1))._mod(i$43)).__nonzero__() ? t$0$PyObject : i$40);
            frame.getlocal(0).invoke("_Random__whseed", new PyObject[] {frame.getlocal(2), frame.getlocal(4), frame.getlocal(3)});
            return Py.None;
        }
        
        private static PyObject __getstate__$10(PyFrame frame) {
            return frame.getlocal(0).invoke("getstate");
        }
        
        private static PyObject __setstate__$11(PyFrame frame) {
            frame.getlocal(0).invoke("setstate", frame.getlocal(1));
            return Py.None;
        }
        
        private static PyObject randrange$12(PyFrame frame) {
            /* Choose a random item from range(start, stop[, step]).
            
                    This fixes the problem with randint() which includes the
                    endpoint; in Python this is usually not what you want.
                    Do not supply the 'int' and 'default' arguments.
                     */
            frame.setlocal(8, frame.getlocal(4).__call__(frame.getlocal(1)));
            if (frame.getlocal(8)._ne(frame.getlocal(1)).__nonzero__()) {
                throw Py.makeException(frame.getglobal("ValueError"), s$72);
            }
            if (frame.getlocal(2)._is(frame.getlocal(5)).__nonzero__()) {
                if (frame.getlocal(8)._gt(i$61).__nonzero__()) {
                    return frame.getlocal(4).__call__(frame.getlocal(0).invoke("random")._mul(frame.getlocal(8)));
                }
                throw Py.makeException(frame.getglobal("ValueError"), s$73);
            }
            frame.setlocal(9, frame.getlocal(4).__call__(frame.getlocal(2)));
            if (frame.getlocal(9)._ne(frame.getlocal(2)).__nonzero__()) {
                throw Py.makeException(frame.getglobal("ValueError"), s$74);
            }
            if (frame.getlocal(3)._eq(i$40).__nonzero__()) {
                if (frame.getlocal(8)._lt(frame.getlocal(9)).__nonzero__()) {
                    return frame.getlocal(8)._add(frame.getlocal(4).__call__(frame.getlocal(0).invoke("random")._mul(frame.getlocal(9)._sub(frame.getlocal(8)))));
                }
                throw Py.makeException(frame.getglobal("ValueError"), s$73);
            }
            frame.setlocal(6, frame.getlocal(4).__call__(frame.getlocal(3)));
            if (frame.getlocal(6)._ne(frame.getlocal(3)).__nonzero__()) {
                throw Py.makeException(frame.getglobal("ValueError"), s$75);
            }
            if (frame.getlocal(6)._gt(i$61).__nonzero__()) {
                frame.setlocal(7, frame.getlocal(9)._sub(frame.getlocal(8))._add(frame.getlocal(6))._sub(i$40)._div(frame.getlocal(6)));
            }
            else if (frame.getlocal(6)._lt(i$61).__nonzero__()) {
                frame.setlocal(7, frame.getlocal(9)._sub(frame.getlocal(8))._add(frame.getlocal(6))._add(i$40)._div(frame.getlocal(6)));
            }
            else {
                throw Py.makeException(frame.getglobal("ValueError"), s$76);
            }
            if (frame.getlocal(7)._le(i$61).__nonzero__()) {
                throw Py.makeException(frame.getglobal("ValueError"), s$73);
            }
            return frame.getlocal(8)._add(frame.getlocal(6)._mul(frame.getlocal(4).__call__(frame.getlocal(0).invoke("random")._mul(frame.getlocal(7)))));
        }
        
        private static PyObject randint$13(PyFrame frame) {
            /* Return random integer in range [a, b], including both end points.
            
                    (Deprecated; use randrange(a, b+1).)
                     */
            return frame.getlocal(0).invoke("randrange", frame.getlocal(1), frame.getlocal(2)._add(i$40));
        }
        
        private static PyObject choice$14(PyFrame frame) {
            /* Choose a random element from a non-empty sequence. */
            return frame.getlocal(1).__getitem__(frame.getglobal("int").__call__(frame.getlocal(0).invoke("random")._mul(frame.getglobal("len").__call__(frame.getlocal(1)))));
        }
        
        private static PyObject shuffle$15(PyFrame frame) {
            // Temporary Variables
            int t$0$int;
            PyObject[] t$0$PyObject__;
            PyObject t$0$PyObject, t$1$PyObject;
            
            // Code
            /* x, random=random.random -> shuffle list x in place; return None.
            
                    Optional arg random is a 0-argument function returning a random
                    float in [0.0, 1.0); by default, the standard random.random.
            
                    Note that for even rather small len(x), the total number of
                    permutations of x is larger than the period of most random number
                    generators; this implies that "most" permutations of a long
                    sequence can never be generated.
                     */
            if (frame.getlocal(2)._is(frame.getglobal("None")).__nonzero__()) {
                frame.setlocal(2, frame.getlocal(0).__getattr__("random"));
            }
            t$0$int = 0;
            t$1$PyObject = frame.getglobal("xrange").__call__(frame.getglobal("len").__call__(frame.getlocal(1))._sub(i$40), i$61, i$40.__neg__());
            while ((t$0$PyObject = t$1$PyObject.__finditem__(t$0$int++)) != null) {
                frame.setlocal(5, t$0$PyObject);
                frame.setlocal(4, frame.getlocal(3).__call__(frame.getlocal(2).__call__()._mul(frame.getlocal(5)._add(i$40))));
                t$0$PyObject__ = org.python.core.Py.unpackSequence(new PyTuple(new PyObject[] {frame.getlocal(1).__getitem__(frame.getlocal(4)), frame.getlocal(1).__getitem__(frame.getlocal(5))}), 2);
                frame.getlocal(1).__setitem__(frame.getlocal(5), t$0$PyObject__[0]);
                frame.getlocal(1).__setitem__(frame.getlocal(4), t$0$PyObject__[1]);
            }
            return Py.None;
        }
        
        private static PyObject uniform$16(PyFrame frame) {
            /* Get a random number in the range [a, b). */
            return frame.getlocal(1)._add(frame.getlocal(2)._sub(frame.getlocal(1))._mul(frame.getlocal(0).invoke("random")));
        }
        
        private static PyObject normalvariate$17(PyFrame frame) {
            frame.setlocal(5, frame.getlocal(0).__getattr__("random"));
            while (i$40.__nonzero__()) {
                frame.setlocal(4, frame.getlocal(5).__call__());
                frame.setlocal(3, frame.getlocal(5).__call__());
                frame.setlocal(7, frame.getglobal("NV_MAGICCONST")._mul(frame.getlocal(4)._sub(f$27))._div(frame.getlocal(3)));
                frame.setlocal(6, frame.getlocal(7)._mul(frame.getlocal(7))._div(f$33));
                if (frame.getlocal(6)._le(frame.getglobal("_log").__call__(frame.getlocal(3)).__neg__()).__nonzero__()) {
                    break;
                }
            }
            return frame.getlocal(1)._add(frame.getlocal(7)._mul(frame.getlocal(2)));
        }
        
        private static PyObject lognormvariate$18(PyFrame frame) {
            return frame.getglobal("_exp").__call__(frame.getlocal(0).invoke("normalvariate", frame.getlocal(1), frame.getlocal(2)));
        }
        
        private static PyObject cunifvariate$19(PyFrame frame) {
            return frame.getlocal(1)._add(frame.getlocal(2)._mul(frame.getlocal(0).invoke("random")._sub(f$27)))._mod(frame.getglobal("_pi"));
        }
        
        private static PyObject expovariate$20(PyFrame frame) {
            frame.setlocal(3, frame.getlocal(0).__getattr__("random"));
            frame.setlocal(2, frame.getlocal(3).__call__());
            while (frame.getlocal(2)._le(f$24).__nonzero__()) {
                frame.setlocal(2, frame.getlocal(3).__call__());
            }
            return frame.getglobal("_log").__call__(frame.getlocal(2)).__neg__()._div(frame.getlocal(1));
        }
        
        private static PyObject vonmisesvariate$21(PyFrame frame) {
            // Temporary Variables
            PyObject t$0$PyObject;
            
            // Code
            frame.setlocal(3, frame.getlocal(0).__getattr__("random"));
            if (frame.getlocal(2)._le(f$81).__nonzero__()) {
                return frame.getglobal("TWOPI")._mul(frame.getlocal(3).__call__());
            }
            frame.setlocal(13, f$36._add(frame.getglobal("_sqrt").__call__(f$36._add(f$33._mul(frame.getlocal(2))._mul(frame.getlocal(2))))));
            frame.setlocal(12, frame.getlocal(13)._sub(frame.getglobal("_sqrt").__call__(f$28._mul(frame.getlocal(13))))._div(f$28._mul(frame.getlocal(2))));
            frame.setlocal(6, f$36._add(frame.getlocal(12)._mul(frame.getlocal(12)))._div(f$28._mul(frame.getlocal(12))));
            while (i$40.__nonzero__()) {
                frame.setlocal(9, frame.getlocal(3).__call__());
                frame.setlocal(5, frame.getglobal("_cos").__call__(frame.getglobal("_pi")._mul(frame.getlocal(9))));
                frame.setlocal(10, f$36._add(frame.getlocal(6)._mul(frame.getlocal(5)))._div(frame.getlocal(6)._add(frame.getlocal(5))));
                frame.setlocal(11, frame.getlocal(2)._mul(frame.getlocal(6)._sub(frame.getlocal(10))));
                frame.setlocal(8, frame.getlocal(3).__call__());
                if (((t$0$PyObject = frame.getlocal(8)._ge(frame.getlocal(11)._mul(f$28._sub(frame.getlocal(11))))).__nonzero__() ? frame.getlocal(8)._gt(frame.getlocal(11)._mul(frame.getglobal("_exp").__call__(f$36._sub(frame.getlocal(11))))) : t$0$PyObject).__not__().__nonzero__()) {
                    break;
                }
            }
            frame.setlocal(7, frame.getlocal(3).__call__());
            if (frame.getlocal(7)._gt(f$27).__nonzero__()) {
                frame.setlocal(4, frame.getlocal(1)._mod(frame.getglobal("TWOPI"))._add(frame.getglobal("_acos").__call__(frame.getlocal(10))));
            }
            else {
                frame.setlocal(4, frame.getlocal(1)._mod(frame.getglobal("TWOPI"))._sub(frame.getglobal("_acos").__call__(frame.getlocal(10))));
            }
            return frame.getlocal(4);
        }
        
        private static PyObject gammavariate$22(PyFrame frame) {
            frame.setlocal(3, frame.getglobal("_sqrt").__call__(f$28._mul(frame.getlocal(1))._sub(f$36)));
            return frame.getlocal(2)._mul(frame.getlocal(0).invoke("stdgamma", new PyObject[] {frame.getlocal(1), frame.getlocal(3), frame.getlocal(1)._sub(frame.getglobal("LOG4")), frame.getlocal(1)._add(frame.getlocal(3))}));
        }
        
        private static PyObject stdgamma$23(PyFrame frame) {
            // Temporary Variables
            PyObject t$0$PyObject, t$1$PyObject;
            
            // Code
            frame.setlocal(5, frame.getlocal(0).__getattr__("random"));
            if (frame.getlocal(1)._le(f$82).__nonzero__()) {
                throw Py.makeException(frame.getglobal("ValueError"), s$83);
            }
            if (frame.getlocal(1)._gt(f$36).__nonzero__()) {
                while (i$40.__nonzero__()) {
                    frame.setlocal(13, frame.getlocal(5).__call__());
                    frame.setlocal(12, frame.getlocal(5).__call__());
                    frame.setlocal(8, frame.getglobal("_log").__call__(frame.getlocal(13)._div(f$36._sub(frame.getlocal(13))))._div(frame.getlocal(2)));
                    frame.setlocal(7, frame.getlocal(1)._mul(frame.getglobal("_exp").__call__(frame.getlocal(8))));
                    frame.setlocal(6, frame.getlocal(13)._mul(frame.getlocal(13))._mul(frame.getlocal(12)));
                    frame.setlocal(10, frame.getlocal(3)._add(frame.getlocal(4)._mul(frame.getlocal(8)))._sub(frame.getlocal(7)));
                    if (((t$0$PyObject = frame.getlocal(10)._add(frame.getglobal("SG_MAGICCONST"))._sub(f$37._mul(frame.getlocal(6)))._ge(f$82)).__nonzero__() ? t$0$PyObject : frame.getlocal(10)._ge(frame.getglobal("_log").__call__(frame.getlocal(6)))).__nonzero__()) {
                        return frame.getlocal(7);
                    }
                }
            }
            else if (frame.getlocal(1)._eq(f$36).__nonzero__()) {
                frame.setlocal(9, frame.getlocal(5).__call__());
                while (frame.getlocal(9)._le(f$24).__nonzero__()) {
                    frame.setlocal(9, frame.getlocal(5).__call__());
                }
                return frame.getglobal("_log").__call__(frame.getlocal(9)).__neg__();
            }
            else {
                while (i$40.__nonzero__()) {
                    frame.setlocal(9, frame.getlocal(5).__call__());
                    frame.setlocal(14, frame.getglobal("_e")._add(frame.getlocal(1))._div(frame.getglobal("_e")));
                    frame.setlocal(11, frame.getlocal(14)._mul(frame.getlocal(9)));
                    if (frame.getlocal(11)._le(f$36).__nonzero__()) {
                        frame.setlocal(7, frame.getglobal("pow").__call__(frame.getlocal(11), f$36._div(frame.getlocal(1))));
                    }
                    else {
                        frame.setlocal(7, frame.getglobal("_log").__call__(frame.getlocal(14)._sub(frame.getlocal(11))._div(frame.getlocal(1))).__neg__());
                    }
                    frame.setlocal(13, frame.getlocal(5).__call__());
                    if (((t$0$PyObject = ((t$1$PyObject = frame.getlocal(11)._le(f$36)).__nonzero__() ? frame.getlocal(13)._gt(frame.getglobal("_exp").__call__(frame.getlocal(7).__neg__())) : t$1$PyObject)).__nonzero__() ? t$0$PyObject : ((t$1$PyObject = frame.getlocal(11)._gt(i$40)).__nonzero__() ? frame.getlocal(13)._gt(frame.getglobal("pow").__call__(frame.getlocal(7), frame.getlocal(1)._sub(f$36))) : t$1$PyObject)).__not__().__nonzero__()) {
                        break;
                    }
                }
                return frame.getlocal(7);
            }
            return Py.None;
        }
        
        private static PyObject gauss$24(PyFrame frame) {
            frame.setlocal(4, frame.getlocal(0).__getattr__("random"));
            frame.setlocal(6, frame.getlocal(0).__getattr__("gauss_next"));
            frame.getlocal(0).__setattr__("gauss_next", frame.getglobal("None"));
            if (frame.getlocal(6)._is(frame.getglobal("None")).__nonzero__()) {
                frame.setlocal(3, frame.getlocal(4).__call__()._mul(frame.getglobal("TWOPI")));
                frame.setlocal(5, frame.getglobal("_sqrt").__call__(f$28.__neg__()._mul(frame.getglobal("_log").__call__(f$36._sub(frame.getlocal(4).__call__())))));
                frame.setlocal(6, frame.getglobal("_cos").__call__(frame.getlocal(3))._mul(frame.getlocal(5)));
                frame.getlocal(0).__setattr__("gauss_next", frame.getglobal("_sin").__call__(frame.getlocal(3))._mul(frame.getlocal(5)));
            }
            return frame.getlocal(1)._add(frame.getlocal(6)._mul(frame.getlocal(2)));
        }
        
        private static PyObject betavariate$25(PyFrame frame) {
            frame.setlocal(3, frame.getlocal(0).invoke("gammavariate", frame.getlocal(1), f$36));
            if (frame.getlocal(3)._eq(i$61).__nonzero__()) {
                return f$82;
            }
            else {
                return frame.getlocal(3)._div(frame.getlocal(3)._add(frame.getlocal(0).invoke("gammavariate", frame.getlocal(2), f$36)));
            }
        }
        
        private static PyObject paretovariate$26(PyFrame frame) {
            frame.setlocal(2, frame.getlocal(0).invoke("random"));
            return f$36._div(frame.getglobal("pow").__call__(frame.getlocal(2), f$36._div(frame.getlocal(1))));
        }
        
        private static PyObject weibullvariate$27(PyFrame frame) {
            frame.setlocal(3, frame.getlocal(0).invoke("random"));
            return frame.getlocal(1)._mul(frame.getglobal("pow").__call__(frame.getglobal("_log").__call__(frame.getlocal(3)).__neg__(), f$36._div(frame.getlocal(2))));
        }
        
        private static PyObject Random$28(PyFrame frame) {
            frame.setlocal("VERSION", i$40);
            frame.setlocal("__init__", new PyFunction(frame.f_globals, new PyObject[] {frame.getname("None")}, c$1___init__));
            frame.setlocal("seed", new PyFunction(frame.f_globals, new PyObject[] {frame.getname("None")}, c$2_seed));
            frame.setlocal("random", new PyFunction(frame.f_globals, new PyObject[] {}, c$3_random));
            frame.setlocal("getstate", new PyFunction(frame.f_globals, new PyObject[] {}, c$4_getstate));
            frame.setlocal("setstate", new PyFunction(frame.f_globals, new PyObject[] {}, c$5_setstate));
            frame.setlocal("jumpahead", new PyFunction(frame.f_globals, new PyObject[] {}, c$6_jumpahead));
            frame.setlocal("_Random__whseed", new PyFunction(frame.f_globals, new PyObject[] {i$61, i$61, i$61}, c$7__Random__whseed));
            frame.setlocal("whseed", new PyFunction(frame.f_globals, new PyObject[] {frame.getname("None")}, c$8_whseed));
            frame.setlocal("__getstate__", new PyFunction(frame.f_globals, new PyObject[] {}, c$9___getstate__));
            frame.setlocal("__setstate__", new PyFunction(frame.f_globals, new PyObject[] {}, c$10___setstate__));
            frame.setlocal("randrange", new PyFunction(frame.f_globals, new PyObject[] {frame.getname("None"), i$40, frame.getname("int"), frame.getname("None")}, c$11_randrange));
            frame.setlocal("randint", new PyFunction(frame.f_globals, new PyObject[] {}, c$12_randint));
            frame.setlocal("choice", new PyFunction(frame.f_globals, new PyObject[] {}, c$13_choice));
            frame.setlocal("shuffle", new PyFunction(frame.f_globals, new PyObject[] {frame.getname("None"), frame.getname("int")}, c$14_shuffle));
            frame.setlocal("uniform", new PyFunction(frame.f_globals, new PyObject[] {}, c$15_uniform));
            frame.setlocal("normalvariate", new PyFunction(frame.f_globals, new PyObject[] {}, c$16_normalvariate));
            frame.setlocal("lognormvariate", new PyFunction(frame.f_globals, new PyObject[] {}, c$17_lognormvariate));
            frame.setlocal("cunifvariate", new PyFunction(frame.f_globals, new PyObject[] {}, c$18_cunifvariate));
            frame.setlocal("expovariate", new PyFunction(frame.f_globals, new PyObject[] {}, c$19_expovariate));
            frame.setlocal("vonmisesvariate", new PyFunction(frame.f_globals, new PyObject[] {}, c$20_vonmisesvariate));
            frame.setlocal("gammavariate", new PyFunction(frame.f_globals, new PyObject[] {}, c$21_gammavariate));
            frame.setlocal("stdgamma", new PyFunction(frame.f_globals, new PyObject[] {}, c$22_stdgamma));
            frame.setlocal("gauss", new PyFunction(frame.f_globals, new PyObject[] {}, c$23_gauss));
            frame.setlocal("betavariate", new PyFunction(frame.f_globals, new PyObject[] {}, c$24_betavariate));
            frame.setlocal("paretovariate", new PyFunction(frame.f_globals, new PyObject[] {}, c$25_paretovariate));
            frame.setlocal("weibullvariate", new PyFunction(frame.f_globals, new PyObject[] {}, c$26_weibullvariate));
            return frame.getf_locals();
        }
        
        private static PyObject _test_generator$29(PyFrame frame) {
            // Temporary Variables
            int t$0$int;
            PyObject t$0$PyObject, t$1$PyObject;
            
            // Code
            frame.setlocal(6, org.python.core.imp.importOne("time", frame));
            Py.printComma(frame.getlocal(0));
            Py.printComma(s$84);
            Py.println(frame.getlocal(1));
            frame.setlocal(3, frame.getglobal("compile").__call__(frame.getlocal(1), frame.getlocal(1), s$85));
            frame.setlocal(4, f$82);
            frame.setlocal(13, f$82);
            frame.setlocal(2, f$86);
            frame.setlocal(5, f$86.__neg__());
            frame.setlocal(9, frame.getlocal(6).__getattr__("time").__call__());
            t$0$int = 0;
            t$1$PyObject = frame.getglobal("range").__call__(frame.getlocal(0));
            while ((t$0$PyObject = t$1$PyObject.__finditem__(t$0$int++)) != null) {
                frame.setlocal(11, t$0$PyObject);
                frame.setlocal(7, frame.getglobal("eval").__call__(frame.getlocal(3)));
                frame.setlocal(4, frame.getlocal(4)._add(frame.getlocal(7)));
                frame.setlocal(13, frame.getlocal(13)._add(frame.getlocal(7)._mul(frame.getlocal(7))));
                frame.setlocal(2, frame.getglobal("min").__call__(frame.getlocal(7), frame.getlocal(2)));
                frame.setlocal(5, frame.getglobal("max").__call__(frame.getlocal(7), frame.getlocal(5)));
            }
            frame.setlocal(8, frame.getlocal(6).__getattr__("time").__call__());
            Py.printComma(frame.getglobal("round").__call__(frame.getlocal(8)._sub(frame.getlocal(9)), i$44));
            Py.printComma(s$87);
            frame.setlocal(10, frame.getlocal(4)._div(frame.getlocal(0)));
            frame.setlocal(12, frame.getglobal("_sqrt").__call__(frame.getlocal(13)._div(frame.getlocal(0))._sub(frame.getlocal(10)._mul(frame.getlocal(10)))));
            Py.println(s$88._mod(new PyTuple(new PyObject[] {frame.getlocal(10), frame.getlocal(12), frame.getlocal(2), frame.getlocal(5)})));
            return Py.None;
        }
        
        private static PyObject _test$30(PyFrame frame) {
            // Temporary Variables
            int t$0$int;
            PyObject t$0$PyObject, t$1$PyObject;
            
            // Code
            Py.printComma(s$89);
            Py.println(frame.getglobal("TWOPI"));
            Py.printComma(s$90);
            Py.println(frame.getglobal("LOG4"));
            Py.printComma(s$91);
            Py.println(frame.getglobal("NV_MAGICCONST"));
            Py.printComma(s$92);
            Py.println(frame.getglobal("SG_MAGICCONST"));
            frame.getglobal("_test_generator").__call__(frame.getlocal(0), s$93);
            frame.getglobal("_test_generator").__call__(frame.getlocal(0), s$94);
            frame.getglobal("_test_generator").__call__(frame.getlocal(0), s$95);
            frame.getglobal("_test_generator").__call__(frame.getlocal(0), s$96);
            frame.getglobal("_test_generator").__call__(frame.getlocal(0), s$97);
            frame.getglobal("_test_generator").__call__(frame.getlocal(0), s$98);
            frame.getglobal("_test_generator").__call__(frame.getlocal(0), s$99);
            frame.getglobal("_test_generator").__call__(frame.getlocal(0), s$100);
            frame.getglobal("_test_generator").__call__(frame.getlocal(0), s$101);
            frame.getglobal("_test_generator").__call__(frame.getlocal(0), s$102);
            frame.getglobal("_test_generator").__call__(frame.getlocal(0), s$103);
            frame.getglobal("_test_generator").__call__(frame.getlocal(0), s$104);
            frame.getglobal("_test_generator").__call__(frame.getlocal(0), s$105);
            frame.getglobal("_test_generator").__call__(frame.getlocal(0), s$106);
            frame.getglobal("_test_generator").__call__(frame.getlocal(0), s$107);
            frame.getglobal("_test_generator").__call__(frame.getlocal(0), s$108);
            frame.setlocal(4, frame.getglobal("getstate").__call__());
            frame.getglobal("jumpahead").__call__(frame.getlocal(0));
            frame.setlocal(2, frame.getglobal("random").__call__());
            frame.getglobal("setstate").__call__(frame.getlocal(4));
            t$0$int = 0;
            t$1$PyObject = frame.getglobal("range").__call__(frame.getlocal(0));
            while ((t$0$PyObject = t$1$PyObject.__finditem__(t$0$int++)) != null) {
                frame.setlocal(3, t$0$PyObject);
                frame.getglobal("random").__call__();
            }
            frame.setlocal(1, frame.getglobal("random").__call__());
            if (frame.getlocal(2)._ne(frame.getlocal(1)).__nonzero__()) {
                throw Py.makeException(frame.getglobal("ValueError").__call__(s$109._add(new PyTuple(new PyObject[] {frame.getlocal(0), frame.getlocal(2), frame.getlocal(1)}).__repr__())));
            }
            return Py.None;
        }
        
        private static PyObject main$31(PyFrame frame) {
            frame.setglobal("__file__", s$112);
            
            PyObject[] imp_accu;
            // Code
            /* Random variable generators.
            
                integers
                --------
                       uniform within range
            
                sequences
                ---------
                       pick random element
                       generate random permutation
            
                distributions on the real line:
                ------------------------------
                       uniform
                       normal (Gaussian)
                       lognormal
                       negative exponential
                       gamma
                       beta
            
                distributions on the circle (angles 0 to 2pi)
                ---------------------------------------------
                       circular uniform
                       von Mises
            
            Translated from anonymously contributed C/C++ source.
            
            Multi-threading note:  the random number generator used here is not thread-
            safe; it is possible that two calls return the same random value.  However,
            you can instantiate a different instance of Random() in each thread to get
            generators that don't share state, then use .setstate() and .jumpahead() to
            move the generators to disjoint segments of the full period.  For example,
            
            def create_generators(num, delta, firstseed=None):
                """Return list of num distinct generators.
                Each generator has its own unique segment of delta elements from
                Random.random()'s full period.
                Seed the first generator with optional arg firstseed (default is
                None, to seed from current time).
                """
            
                from random import Random
                g = Random(firstseed)
                result = [g]
                for i in range(num - 1):
                    laststate = g.getstate()
                    g = Random()
                    g.setstate(laststate)
                    g.jumpahead(delta)
                    result.append(g)
                return result
            
            gens = create_generators(10, 1000000)
            
            That creates 10 distinct generators, which can be passed out to 10 distinct
            threads.  The generators don't share state so can be called safely in
            parallel.  So long as no thread calls its g.random() more than a million
            times (the second argument to create_generators), the sequences seen by
            each thread will not overlap.
            
            The period of the underlying Wichmann-Hill generator is 6,953,607,871,644,
            and that limits how far this technique can be pushed.
            
            Just for fun, note that since we know the period, .jumpahead() can also be
            used to "move backward in time":
            
            >>> g = Random(42)  # arbitrary
            >>> g.random()
            0.25420336316883324
            >>> g.jumpahead(6953607871644L - 1) # move *back* one
            >>> g.random()
            0.25420336316883324
             */
            imp_accu = org.python.core.imp.importFrom("math", new String[] {"log", "exp", "pi", "e"}, frame);
            frame.setlocal("_log", imp_accu[0]);
            frame.setlocal("_exp", imp_accu[1]);
            frame.setlocal("_pi", imp_accu[2]);
            frame.setlocal("_e", imp_accu[3]);
            imp_accu = null;
            imp_accu = org.python.core.imp.importFrom("math", new String[] {"sqrt", "acos", "cos", "sin"}, frame);
            frame.setlocal("_sqrt", imp_accu[0]);
            frame.setlocal("_acos", imp_accu[1]);
            frame.setlocal("_cos", imp_accu[2]);
            frame.setlocal("_sin", imp_accu[3]);
            imp_accu = null;
            frame.setlocal("__all__", new PyList(new PyObject[] {s$1, s$2, s$3, s$4, s$5, s$6, s$7, s$8, s$9, s$10, s$11, s$12, s$13, s$14, s$15, s$16, s$17, s$18, s$19, s$20, s$21, s$22, s$23}));
            frame.setlocal("_verify", new PyFunction(frame.f_globals, new PyObject[] {}, c$0__verify));
            frame.setlocal("NV_MAGICCONST", i$26._mul(frame.getname("_exp").__call__(f$27.__neg__()))._div(frame.getname("_sqrt").__call__(f$28)));
            frame.getname("_verify").__call__(s$29, frame.getname("NV_MAGICCONST"), f$30);
            frame.setlocal("TWOPI", f$28._mul(frame.getname("_pi")));
            frame.getname("_verify").__call__(s$31, frame.getname("TWOPI"), f$32);
            frame.setlocal("LOG4", frame.getname("_log").__call__(f$33));
            frame.getname("_verify").__call__(s$34, frame.getname("LOG4"), f$35);
            frame.setlocal("SG_MAGICCONST", f$36._add(frame.getname("_log").__call__(f$37)));
            frame.getname("_verify").__call__(s$38, frame.getname("SG_MAGICCONST"), f$39);
            frame.dellocal("_verify");
            frame.setlocal("Random", Py.makeClass("Random", new PyObject[] {}, c$27_Random, null));
            frame.setlocal("_test_generator", new PyFunction(frame.f_globals, new PyObject[] {}, c$28__test_generator));
            frame.setlocal("_test", new PyFunction(frame.f_globals, new PyObject[] {i$110}, c$29__test));
            frame.setlocal("_inst", frame.getname("Random").__call__());
            frame.setlocal("seed", frame.getname("_inst").__getattr__("seed"));
            frame.setlocal("random", frame.getname("_inst").__getattr__("random"));
            frame.setlocal("uniform", frame.getname("_inst").__getattr__("uniform"));
            frame.setlocal("randint", frame.getname("_inst").__getattr__("randint"));
            frame.setlocal("choice", frame.getname("_inst").__getattr__("choice"));
            frame.setlocal("randrange", frame.getname("_inst").__getattr__("randrange"));
            frame.setlocal("shuffle", frame.getname("_inst").__getattr__("shuffle"));
            frame.setlocal("normalvariate", frame.getname("_inst").__getattr__("normalvariate"));
            frame.setlocal("lognormvariate", frame.getname("_inst").__getattr__("lognormvariate"));
            frame.setlocal("cunifvariate", frame.getname("_inst").__getattr__("cunifvariate"));
            frame.setlocal("expovariate", frame.getname("_inst").__getattr__("expovariate"));
            frame.setlocal("vonmisesvariate", frame.getname("_inst").__getattr__("vonmisesvariate"));
            frame.setlocal("gammavariate", frame.getname("_inst").__getattr__("gammavariate"));
            frame.setlocal("stdgamma", frame.getname("_inst").__getattr__("stdgamma"));
            frame.setlocal("gauss", frame.getname("_inst").__getattr__("gauss"));
            frame.setlocal("betavariate", frame.getname("_inst").__getattr__("betavariate"));
            frame.setlocal("paretovariate", frame.getname("_inst").__getattr__("paretovariate"));
            frame.setlocal("weibullvariate", frame.getname("_inst").__getattr__("weibullvariate"));
            frame.setlocal("getstate", frame.getname("_inst").__getattr__("getstate"));
            frame.setlocal("setstate", frame.getname("_inst").__getattr__("setstate"));
            frame.setlocal("jumpahead", frame.getname("_inst").__getattr__("jumpahead"));
            frame.setlocal("whseed", frame.getname("_inst").__getattr__("whseed"));
            if (frame.getname("__name__")._eq(s$111).__nonzero__()) {
                frame.getname("_test").__call__();
            }
            return Py.None;
        }
        
    }
    public static void moduleDictInit(PyObject dict) {
        dict.__setitem__("__name__", new PyString("random"));
        Py.runCode(new _PyInner().getMain(), dict, dict);
    }
    
    public static void main(String[] args) throws java.lang.Exception {
        String[] newargs = new String[args.length+1];
        newargs[0] = "random";
        System.arraycopy(args, 0, newargs, 1, args.length);
        Py.runMain(random._PyInner.class, newargs, random.jpy$packages, random.jpy$mainProperties, "", new String[] {"string", "random", "util", "traceback", "sre_compile", "atexit", "sre", "sre_constants", "StringIO", "javaos", "socket", "yapm", "calendar", "repr", "copy_reg", "SocketServer", "server", "re", "linecache", "javapath", "UserDict", "copy", "threading", "stat", "PathVFS", "sre_parse"});
    }
    
}
